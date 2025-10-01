import Foundation
import HealthKit
import Combine
import UIKit

class VitalsSyncManager: ObservableObject {
    // MARK: - Components
    private let networkMonitor = VitalsNetworkMonitor()
    private let progressTracker = VitalsSyncProgress()
    private let persistence = VitalsSyncPersistence()
    let dataProcessor = VitalsDataProcessor()
    
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: - Published Properties (delegated to components)
    @Published var isNetworkAvailable = true
    @Published var isSyncing = false
    @Published var syncProgress: Double = 0.0
    @Published var syncMessage = "Ready to sync"
    @Published var totalDataPoints: Int = 0
    @Published var syncedDataPoints: Int = 0
    @Published var currentMetricBeingSynced: String = ""
    @Published var errorMessage: String?
    
    // MARK: - State Management
    private var pendingSubmissions: [VitalDataSubmission] = []
    private var completedChunks: Int = 0
    private var syncStartDate: Date?
    private var syncEndDate: Date?
    private var syncType: SyncType = .initial
    private let syncCooldownInterval: TimeInterval = 30
    
    weak var vitalsManager: BackendVitalsManager?
    
    // MARK: - Initialization
    
    init(vitalsManager: BackendVitalsManager) {
        self.vitalsManager = vitalsManager
        setupComponentBindings()
        setupNetworkCallbacks()
        restoreProgressIfNeeded()
    }
    
    private func setupComponentBindings() {
        // Bind network monitor to published properties
        networkMonitor.$isNetworkAvailable
            .assign(to: \.isNetworkAvailable, on: self)
            .store(in: &cancellables)
        
        // Bind progress tracker to published properties
        progressTracker.$isSyncing
            .assign(to: \.isSyncing, on: self)
            .store(in: &cancellables)
        
        progressTracker.$syncProgress
            .assign(to: \.syncProgress, on: self)
            .store(in: &cancellables)
        
        progressTracker.$syncMessage
            .assign(to: \.syncMessage, on: self)
            .store(in: &cancellables)
        
        progressTracker.$totalDataPoints
            .assign(to: \.totalDataPoints, on: self)
            .store(in: &cancellables)
        
        progressTracker.$syncedDataPoints
            .assign(to: \.syncedDataPoints, on: self)
            .store(in: &cancellables)
        
        progressTracker.$currentMetricBeingSynced
            .assign(to: \.currentMetricBeingSynced, on: self)
            .store(in: &cancellables)
        
        progressTracker.$errorMessage
            .assign(to: \.errorMessage, on: self)
            .store(in: &cancellables)
    }
    
    private func setupNetworkCallbacks() {
        networkMonitor.onNetworkRestored = { [weak self] in
            self?.checkForNewDataAndSync()
        }
        
        networkMonitor.onRetrySync = { [weak self] in
            self?.performNetworkRetrySync()
        }
        
        networkMonitor.onNetworkLost = { [weak self] in
            // Network lost handling is automatic through the monitor
        }
    }
    
    // MARK: - Public Interface
    
    func isNetworkConnected() -> Bool {
        return networkMonitor.isNetworkAvailable
    }
    
    func hasFailedSyncPendingRetry() -> Bool {
        return networkMonitor.hasFailedSyncPendingRetry()
    }
    
    func manualRetrySync() {
        networkMonitor.manualRetrySync()
    }
    
    func clearSyncProgress() {
        progressTracker.clearSyncProgress()
        progressTracker.clearPersistedProgressState()
        clearResumableState()
    }
    
    // MARK: - Sync Operations
    
    func performInitialSync() {
        guard canStartSync() else { return }
        
        print("🚀 [VitalsSyncManager] Starting initial sync")
        syncType = .initial
        persistence.saveLastSyncTime(Date())
        
        let endDate = Date()
        let startDate = Calendar.current.date(byAdding: .day, value: -30, to: endDate) ?? endDate
        
        performSync(from: startDate, to: endDate, syncType: .initial)
    }
    
    func performHistoricalSync() {
        guard canStartSync() else { return }
        
        print("🚀 [VitalsSyncManager] Starting historical sync")
        syncType = .historical
        persistence.saveLastSyncTime(Date())
        
        let endDate = Date()
        // Fetch from the beginning of Apple Health data (2014 when HealthKit was introduced)
        let startDate = Calendar.current.date(from: DateComponents(year: 2014, month: 1, day: 1)) ?? endDate
        
        performSync(from: startDate, to: endDate, syncType: .historical)
    }
    
    func performIncrementalSync() {
        guard canStartSync() else { return }
        
        Task {
            do {
                print("🔄 [VitalsSyncManager] Starting intelligent incremental sync")
                syncType = .incremental
                persistence.saveLastSyncTime(Date())
                
                // Use the new gap analysis method
                progressTracker.startSyncProgress()
                progressTracker.updateSyncProgress(current: 0, total: 100, message: "Analyzing data gaps...")
                
                let submissions = try await dataProcessor.fetchVitalDataWithGapAnalysis()
                
                guard !submissions.isEmpty else {
                    progressTracker.completeSyncProgress(success: true, message: "All data is up to date")
                    return
                }
                
                // Submit data
                progressTracker.updateSyncProgress(current: 25, total: 100, message: "Submitting \(submissions.count) data points...")
                
                try await dataProcessor.submitAllData(submissions) { completed, total in
                    let progress = 25 + Int(Double(completed) / Double(total) * 65) // 25-90% for submission
                    DispatchQueue.main.async {
                        self.progressTracker.updateSyncProgress(
                            current: progress,
                            total: 100,
                            message: "Submitted \(completed) of \(total) data points"
                        )
                    }
                }
                
                // Trigger aggregation
                progressTracker.updateSyncProgress(current: 90, total: 100, message: "Triggering data aggregation...")
                await dataProcessor.triggerAggregation()
                
                // Complete
                progressTracker.completeSyncProgress(success: true, message: "Incremental sync completed successfully")
                persistence.saveLastSyncTimestamp(Date(), for: syncType)
                clearResumableState()
                
            } catch {
                DispatchQueue.main.async {
                    self.handleSyncError(error, context: "intelligent incremental sync")
                }
            }
        }
    }
    
    func performLast24HoursSync() {
        guard canStartSync() else { return }
        
        print("🚀 [VitalsSyncManager] Starting last 24 hours sync")
        syncType = .lastTwentyFourHours
        persistence.saveLastSyncTime(Date())
        
        let endDate = Date()
        let startDate = Calendar.current.date(byAdding: .day, value: -1, to: endDate) ?? endDate
        
        performSync(from: startDate, to: endDate, syncType: .lastTwentyFourHours)
    }
    
    // MARK: - Core Sync Logic
    
    private func performSync(from startDate: Date, to endDate: Date, syncType: SyncType) {
        self.syncStartDate = startDate
        self.syncEndDate = endDate
        self.syncType = syncType
        
        progressTracker.startSyncProgress()
        
        Task {
            do {
                // Fetch data
                progressTracker.updateSyncProgress(current: 0, total: 100, message: "Fetching health data...")
                let submissions = try await dataProcessor.fetchVitalData(from: startDate, to: endDate)
                
                guard !submissions.isEmpty else {
                    progressTracker.completeSyncProgress(success: true, message: "No new data to sync")
                    return
                }
                
                // Submit data
                progressTracker.updateSyncProgress(current: 25, total: 100, message: "Submitting \(submissions.count) data points...")
                
                try await dataProcessor.submitAllData(submissions) { completed, total in
                    let progress = 25 + Int(Double(completed) / Double(total) * 65) // 25-90% for submission
            DispatchQueue.main.async {
                        self.progressTracker.updateSyncProgress(
                            current: progress,
                            total: 100,
                            message: "Submitted \(completed) of \(total) data points"
                        )
                    }
                }
                
                // Trigger aggregation
                progressTracker.updateSyncProgress(current: 90, total: 100, message: "Triggering data aggregation...")
                await dataProcessor.triggerAggregation()
                
                // Complete
                progressTracker.completeSyncProgress(success: true, message: "Sync completed successfully")
                persistence.saveLastSyncTimestamp(Date(), for: syncType)
                clearResumableState()
                
            } catch {
                handleSyncError(error, context: "sync operation")
            }
        }
    }
    
    // MARK: - Helper Methods
    
    private func canStartSync() -> Bool {
        guard vitalsManager?.isAuthorized == true else {
            print("❌ [VitalsSyncManager] Cannot start sync: HealthKit not authorized")
            return false
        }
        
        guard !isSyncing else {
            print("⚠️ [VitalsSyncManager] Sync already in progress")
            return false
        }
        
        guard !persistence.isSyncOnCooldown(cooldownInterval: syncCooldownInterval) else {
            print("⚠️ [VitalsSyncManager] Sync on cooldown")
            progressTracker.completeSyncProgress(success: false, message: "Please wait before syncing again")
            return false
        }
        
        print("✅ [VitalsSyncManager] All sync preconditions met")
        return true
    }
    
    private func handleSyncError(_ error: Error, context: String) {
        print("❌ [VitalsSyncManager] Sync error in \(context): \(error)")
        if let urlError = error as? URLError {
            print("   URLError details: code=\(urlError.code.rawValue), description=\(urlError.localizedDescription)")
        }
        
        networkMonitor.handleSyncError(error, context: context) { [weak self] message in
            print("🔄 [VitalsSyncManager] Network monitor suggests retry with message: \(message)")
            self?.progressTracker.completeSyncProgress(success: false, message: message)
        } onRetryFailed: { [weak self] message in
            print("❌ [VitalsSyncManager] Network retry failed with message: \(message)")
            self?.progressTracker.completeSyncProgress(success: false, message: message)
            self?.networkMonitor.clearRetryState()
        }
    }
    
    private func performNetworkRetrySync() {
        guard canStartSync() else { return }
        
        print("🔄 [VitalsSyncManager] Performing network retry sync...")
        syncType = .networkRetry
        persistence.saveLastSyncTime(Date())
        progressTracker.startSyncProgress()
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            self.checkSyncStatusAndPerformIncrementalSync()
        }
    }
    
    private func checkSyncStatusAndPerformIncrementalSync() {
        // If we have resumable state, continue from there
        if let resumableState = persistence.loadResumableState() {
            continueResumableSync(from: resumableState)
            } else {
            // Otherwise perform incremental sync
            performIncrementalSync()
        }
    }
    
    private func checkForNewDataAndSync() {
        guard !isSyncing else { return }
        performIncrementalSync()
    }
    
    // MARK: - Resumable Sync Support
    
    private func continueResumableSync(from state: VitalsSyncPersistence.ResumableSyncState) {
        print("🔄 [VitalsSyncManager] Continuing resumable sync with \(state.pendingSubmissions.count) pending submissions")
        
        pendingSubmissions = state.pendingSubmissions
        completedChunks = state.completedChunks
        syncStartDate = state.syncStartDate
        syncEndDate = state.syncEndDate
        syncType = SyncType(rawValue: state.syncType) ?? .incremental
        
        progressTracker.startSyncProgress()
        
        Task {
            do {
                try await dataProcessor.submitAllData(pendingSubmissions) { completed, total in
                        DispatchQueue.main.async {
                        self.progressTracker.updateSyncProgress(
                            current: completed,
                            total: total,
                            message: "Resuming sync: \(completed) of \(total) data points"
                        )
                    }
                }
                
                progressTracker.completeSyncProgress(success: true, message: "Resumable sync completed")
                clearResumableState()
                
            } catch {
                handleSyncError(error, context: "resumable sync")
            }
        }
    }
    
    private func clearResumableState() {
        pendingSubmissions.removeAll()
        completedChunks = 0
        syncStartDate = nil
        syncEndDate = nil
        persistence.clearResumableState()
    }
    
    // MARK: - Progress Restoration
    
    private func restoreProgressIfNeeded() {
        if let progressState = progressTracker.restoreProgressState() {
            // If we had an active sync, try to resume it
            if progressState.isSyncing {
                print("📱 [VitalsSyncManager] Restoring sync progress from previous session")
                checkSyncStatusAndPerformIncrementalSync()
            }
        }
    }
} 