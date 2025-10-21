import Foundation
import HealthKit
import Combine
import UIKit

// BackendVitalsManager: Manages HealthKit integration and backend synchronization

final class BackendVitalsManager: ObservableObject, @unchecked Sendable {
    static let shared = BackendVitalsManager()
    
    private let healthStore = HKHealthStore()
    private let apiService = VitalsAPIService.shared
    private var cancellables = Set<AnyCancellable>()
    private var authStateSubscription: AnyCancellable?
    
    @Published var isAuthorized = false
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var healthMetrics: [HealthMetric] = []
    @Published var dashboardData: VitalDashboard?
    @Published var syncStatus: VitalSyncStatus?
    
    // Sync manager for handling all sync operations
    private var syncManager: VitalsSyncManager!
    
    // Sync settings
    @Published var autoSyncEnabled = true
    @Published var healthKitFeatureEnabled = true
    private var syncTimer: Timer?
    
    // Sync state properties (mirrored from VitalsSyncManager for UI observation)
    @Published var isSyncing: Bool = false
    @Published var syncProgress: Double = 0.0
    @Published var syncMessage: String = ""
    @Published var totalDataPoints: Int = 0
    @Published var syncedDataPoints: Int = 0
    @Published var currentMetricBeingSynced: String = ""
    @Published var isNetworkAvailable: Bool = true
    @Published var hasFailedSyncPendingRetry: Bool = false
    
    // Last dashboard refresh tracking
    private var lastDashboardRefresh: Date?
    private let dashboardCacheTimeout: TimeInterval = 300 // 5 minutes
    
    private init() {
        print("🏥 [BackendVitalsManager] Initializing...")
        syncManager = VitalsSyncManager(vitalsManager: self)
        setupAuthObserver()
        setupSyncObservation()
        refreshDevicesConfig()
        checkAuthorizationStatus()
        setupAutoSync()
        setupPeriodicSync()
        setupBackgroundNotifications()
    }
    
    // MARK: - Auth State Observer
    /// Observe authentication state and clear data on logout
    private func setupAuthObserver() {
        authStateSubscription = NetworkService.shared.$isAuthenticatedState
            .sink { [weak self] isAuthenticated in
                if !isAuthenticated {
                    print("🔒 [BackendVitalsManager] User logged out - clearing vitals data")
                    self?.clearData()
                }
            }
    }
    
    /// Clear all cached data
    private func clearData() {
        DispatchQueue.main.async { [weak self] in
            self?.healthMetrics = []
            self?.dashboardData = nil
            self?.syncStatus = nil
            self?.errorMessage = nil
        }
    }
    
    // MARK: - Sync Observation Setup
    private func setupSyncObservation() {
        // Observe VitalsSyncManager changes and mirror them to our @Published properties
        syncManager.$isSyncing
            .receive(on: DispatchQueue.main)
            .sink { [weak self] value in
                print("🔄 [BackendVitalsManager] Received isSyncing update: \(value)")
                self?.isSyncing = value
            }
            .store(in: &cancellables)
        
        syncManager.$syncProgress
            .receive(on: DispatchQueue.main)
            .sink { [weak self] value in
                print("🔄 [BackendVitalsManager] Received syncProgress update: \(value)")
                self?.syncProgress = value
            }
            .store(in: &cancellables)
        
        syncManager.$syncMessage
            .receive(on: DispatchQueue.main)
            .sink { [weak self] value in
                print("🔄 [BackendVitalsManager] Received syncMessage update: \(value)")
                self?.syncMessage = value
            }
            .store(in: &cancellables)
        
        syncManager.$totalDataPoints
            .receive(on: DispatchQueue.main)
            .sink { [weak self] value in
                self?.totalDataPoints = value
            }
            .store(in: &cancellables)
        
        syncManager.$syncedDataPoints
            .receive(on: DispatchQueue.main)
            .sink { [weak self] value in
                self?.syncedDataPoints = value
            }
            .store(in: &cancellables)
        
        syncManager.$currentMetricBeingSynced
            .receive(on: DispatchQueue.main)
            .sink { [weak self] value in
                self?.currentMetricBeingSynced = value
            }
            .store(in: &cancellables)
        
        syncManager.$isNetworkAvailable
            .receive(on: DispatchQueue.main)
            .sink { [weak self] value in
                self?.isNetworkAvailable = value
            }
            .store(in: &cancellables)
        
        // Observe failed sync state changes
        Timer.publish(every: 1.0, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.hasFailedSyncPendingRetry = self?.syncManager.hasFailedSyncPendingRetry() ?? false
            }
            .store(in: &cancellables)
        
        print("✅ [BackendVitalsManager] Sync observation setup completed")
    }
    
    // MARK: - Public Sync Methods (delegated to syncManager)
    func performInitialSync() {
        syncManager.performInitialSync()
    }
    
    func performIncrementalSync() {
        syncManager.performIncrementalSync()
    }
    
    public func checkForNewDataAndSync() {
        // Smart decision: Historical vs Incremental sync
        Task {
            do {
                let backendTimestamps = try await syncManager.dataProcessor.getLatestBackendTimestamps()
                let syncStrategy = decideSyncStrategy(backendTimestamps: backendTimestamps)
                
                switch syncStrategy {
                case .historical:
                    print("🔍 [BackendVitalsManager] No existing data detected - triggering HISTORICAL SYNC")
                    syncManager.performHistoricalSync()
                case .incremental:
                    print("🔍 [BackendVitalsManager] Existing data detected - triggering INCREMENTAL SYNC")
                    syncManager.performIncrementalSync()
                }
                
                // Refresh dashboard after sync to show updated data in vitals card
                // Add a delay to allow sync to complete and data to be processed
                DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) {
                    print("🔄 [BackendVitalsManager] Refreshing dashboard after sync")
                    self.refreshDashboard()
                }
                
            } catch {
                print("❌ [BackendVitalsManager] Failed to check backend timestamps, defaulting to incremental sync: \(error)")
                syncManager.performIncrementalSync()
                
                // Still refresh dashboard after fallback sync
                DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) {
                    print("🔄 [BackendVitalsManager] Refreshing dashboard after fallback sync")
                    self.refreshDashboard()
                }
            }
        }
    }
    
    // MARK: - Sync Strategy Decision
    
    private enum SyncStrategy {
        case historical  // No data exists, use performHistoricalSync()
        case incremental // Data exists, use performIncrementalSync()
    }
    
    private func decideSyncStrategy(backendTimestamps: [VitalMetricType: Date]) -> SyncStrategy {
        // Define core metrics that should always have data if user has been syncing
        let coreMetrics: [VitalMetricType] = [.heartRate, .stepCount, .activeEnergy, .standTime]
        
        // Check if ANY core metric has existing data
        let hasAnyCoreData = coreMetrics.contains { metricType in
            backendTimestamps[metricType] != nil
        }
        
        if !hasAnyCoreData {
            print("🔍 [BackendVitalsManager] No core metrics data found - HISTORICAL SYNC needed")
            return .historical
        }
        
        // Check if we have very little data (less than 2 core metrics)
        let coreMetricsWithData = coreMetrics.filter { metricType in
            backendTimestamps[metricType] != nil
        }
        
        if coreMetricsWithData.count < 2 {
            print("🔍 [BackendVitalsManager] Only \(coreMetricsWithData.count) core metrics have data - HISTORICAL SYNC needed")
            return .historical
        }
        
        print("🔍 [BackendVitalsManager] \(coreMetricsWithData.count) core metrics have data - INCREMENTAL SYNC appropriate")
        return .incremental
    }
    
    func retryFailedSync() {
        syncManager.manualRetrySync()
    }
    
    // MARK: - Authorization
    
    // Public method to re-check authorization status (useful for UI calls)
    func recheckAuthorizationAndLoadData() {
        print("🔍 [BackendVitalsManager] Rechecking authorization and loading data...")
        checkAuthorizationStatus()
    }
    
    func requestAuthorization() {
        // No-op: Authorization UX is handled in ConnectedDevicesView via HealthKitUI
        print("ℹ️ [BackendVitalsManager] Skipping requestAuthorization - handled by UI flow")
        checkAuthorizationStatus()
    }
    
    private func checkAuthorizationStatus() {
        guard healthKitFeatureEnabled else {
            print("⚠️ [BackendVitalsManager] Skipping authorization status check: feature disabled")
            isAuthorized = false
            return
        }
        
        Task {
            // Read-only status check; no prompts here
            HealthKitAuthorizationService.shared.checkAuthorizationStatus()
            var hkAuthorized = HealthKitAuthorizationService.shared.isAuthorized
            await MainActor.run { self.errorMessage = nil }

            // Also respect the backend device connection toggle as the source of truth for UX
            do {
                let device = try await NetworkService.shared.getDeviceStatus(provider: "healthkit")
                if device.is_connected {
                    hkAuthorized = true
                }
            } catch {
                // Ignore backend read errors here; fall back to HK status only
            }
            await MainActor.run { self.isAuthorized = hkAuthorized }
            
            print("🔍 [BackendVitalsManager] Current HealthKit authorization status: \(HealthKitAuthorizationService.shared.getCurrentAuthorizationStatus().rawValue)")
            let currentAuthorized = await MainActor.run { self.isAuthorized }
            let hasDashboard = await MainActor.run { self.dashboardData != nil }
            print("🔍 [BackendVitalsManager] Current isAuthorized state: \(currentAuthorized)")
            print("🔍 [BackendVitalsManager] Current dashboardData state: \(hasDashboard ? "exists" : "nil")")
            
            if currentAuthorized {
                print("✅ [BackendVitalsManager] HealthKit already authorized - updating state")
                
                // Enable backend sync and refresh dashboard for existing users
                enableBackendSync()
                
                // Force dashboard refresh on startup when already authorized
                print("🔄 [BackendVitalsManager] App startup - forcing dashboard refresh for authorized user")
                self.refreshDashboard()
                
                // Also trigger sync to ensure we have the latest data
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                    print("🔄 [BackendVitalsManager] App startup - triggering data sync")
                    self.checkForNewDataAndSync()
                }
            } else {
                print("❌ [BackendVitalsManager] HealthKit not authorized - awaiting user action in ConnectedDevicesView")
            }
            
            let finalAuth = await MainActor.run { self.isAuthorized }
            print("🔍 [BackendVitalsManager] Final isAuthorized state: \(finalAuth)")
        }
    }
    
    // MARK: - Backend Sync Management
    private func enableBackendSync() {
        apiService.enableSync()
            .sink(
                receiveCompletion: { completion in
                    if case .failure(let error) = completion {
                        print("Failed to enable backend sync: \(error)")
                    }
                },
                receiveValue: { _ in
                    print("Backend sync enabled")
                }
            )
            .store(in: &cancellables)
    }
    
    private func setupAutoSync() {
        // Sync every 15 minutes when app is active
        syncTimer = Timer.scheduledTimer(withTimeInterval: 900, repeats: true) { [weak self] _ in
            if self?.autoSyncEnabled == true && self?.isAuthorized == true {
                self?.performIncrementalSync()
            }
        }
    }
    
    private func setupPeriodicSync() {
        // Setup periodic dashboard refresh
        print("🔄 [BackendVitalsManager] Setting up periodic sync")
    }
    
    // MARK: - Background Task Management
    private func setupBackgroundNotifications() {
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleAppDidEnterBackground),
            name: UIApplication.didEnterBackgroundNotification,
            object: nil
        )
        
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleAppWillEnterForeground),
            name: UIApplication.willEnterForegroundNotification,
            object: nil
        )
    }

    // MARK: - Devices Config
    private func refreshDevicesConfig() {
        Task {
            do {
                let cfg = try await NetworkService.shared.fetchDevicesConfig()
                await MainActor.run {
                    self.healthKitFeatureEnabled = cfg.healthkit_enabled
                }
            } catch {
                // Assume enabled on error to avoid blocking user unexpectedly
                await MainActor.run {
                    self.healthKitFeatureEnabled = true
                }
            }
        }
    }
    
    @objc private func handleAppDidEnterBackground() {
        print("🔄 [BackendVitalsManager] App entered background")
    }
    
    @objc private func handleAppWillEnterForeground() {
        print("🔄 [BackendVitalsManager] App entering foreground - checking for sync needs")
        refreshDevicesConfig()
        
        // Re-check authorization status as it might have changed
        checkAuthorizationStatus()
        
        // Check if we need to sync after returning from background
        if isAuthorized && !isSyncing {
            // Ensure we have dashboard data when coming back to foreground
            if dashboardData == nil {
                print("🔄 [BackendVitalsManager] No dashboard data on foreground - forcing refresh")
                refreshDashboard()
            }
            
            // Small delay to let the app fully restore, then check for new data
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                self.checkForNewDataAndSync()
            }
        }
    }
    
    // MARK: - Dashboard Management
    func refreshDashboard() {
        guard !isLoading else {
            print("⚠️ [BackendVitalsManager] Dashboard refresh already in progress")
            return
        }
        
        DispatchQueue.main.async {
            self.isLoading = true
            self.errorMessage = nil
        }
        
        apiService.getDashboard()
            .sink(
                receiveCompletion: { [weak self] completion in
                    DispatchQueue.main.async {
                        self?.isLoading = false
                    }
                    
                    if case .failure(let error) = completion {
                        print("❌ [BackendVitalsManager] Failed to refresh dashboard: \(error)")
                        
                        // Better error handling for different error types
                        let errorMessage: String
                        if let urlError = error as? URLError {
                            switch urlError.code {
                            case .notConnectedToInternet, .networkConnectionLost:
                                errorMessage = "No internet connection available"
                            case .timedOut:
                                errorMessage = "Connection timed out - please try again"
                            case .cannotConnectToHost, .cannotFindHost:
                                errorMessage = "Cannot connect to server - please check settings"
                            default:
                                errorMessage = "Network error: \(error.localizedDescription)"
                            }
                        } else {
                            errorMessage = "Failed to load dashboard: \(error.localizedDescription)"
                        }
                        
                        DispatchQueue.main.async {
                            self?.errorMessage = errorMessage
                        }
                        
                        // Auto-retry after a delay for network-related errors
                        if let urlError = error as? URLError,
                           [.notConnectedToInternet, .networkConnectionLost, .cannotConnectToHost].contains(urlError.code) {
                            DispatchQueue.main.asyncAfter(deadline: .now() + 10) {
                                self?.checkAndRefreshIfNeeded()
                            }
                        }
                    }
                },
                receiveValue: { [weak self] dashboard in
                    print("✅ [BackendVitalsManager] Dashboard refreshed successfully")
                    DispatchQueue.main.async {
                        self?.dashboardData = dashboard
                        self?.lastDashboardRefresh = Date()
                        self?.errorMessage = nil
                    }
                }
            )
            .store(in: &cancellables)
    }
    
    // MARK: - Async Dashboard Management
    
    func refreshDashboardAsync() async throws {
        guard !isLoading else {
            print("⚠️ [BackendVitalsManager] Dashboard refresh already in progress")
            return
        }
        
        isLoading = true
        errorMessage = nil
        
        do {
            let dashboard = try await apiService.getDashboard()
                .receive(on: DispatchQueue.main)
                .eraseToAnyPublisher()
                .async()
            
            print("✅ [BackendVitalsManager] Dashboard refreshed successfully")
            dashboardData = dashboard
            lastDashboardRefresh = Date()
            errorMessage = nil
            isLoading = false
            
        } catch {
            print("❌ [BackendVitalsManager] Failed to refresh dashboard: \(error)")
            isLoading = false
            
            // Better error handling for different error types
            let errorMessage: String
            if let urlError = error as? URLError {
                switch urlError.code {
                case .notConnectedToInternet, .networkConnectionLost:
                    errorMessage = "No internet connection available"
                case .timedOut:
                    errorMessage = "Connection timed out - please try again"
                case .cannotConnectToHost, .cannotFindHost:
                    errorMessage = "Cannot connect to server - please check settings"
                default:
                    errorMessage = "Network error: \(error.localizedDescription)"
                }
            } else {
                errorMessage = "Failed to load dashboard: \(error.localizedDescription)"
            }
            
            self.errorMessage = errorMessage
            throw error
        }
    }
    

    
    func checkAndRefreshIfNeeded() {
        guard isAuthorized else {
            print("⚠️ [BackendVitalsManager] Cannot refresh dashboard: not authorized")
            return
        }
        
        // Always refresh if we don't have dashboard data
        if dashboardData == nil {
            print("🔄 [BackendVitalsManager] No dashboard data available, refreshing...")
            refreshDashboard()
            return
        }
        
        // Check if we need to refresh based on cache timeout
        if let lastRefresh = lastDashboardRefresh {
            let timeSinceLastRefresh = Date().timeIntervalSince(lastRefresh)
            if timeSinceLastRefresh < dashboardCacheTimeout {
                print("✅ [BackendVitalsManager] Dashboard cache is still valid")
                return
            }
        }
        
        print("🔄 [BackendVitalsManager] Dashboard cache expired or missing, refreshing...")
        refreshDashboard()
    }
    
    // MARK: - Health Metrics Management
    func fetchHealthMetrics() {
        guard isAuthorized else {
            print("❌ [BackendVitalsManager] Cannot fetch health metrics: not authorized")
            return
        }
        
        // This would typically fetch from HealthKit directly for immediate display
        // while the sync process handles backend synchronization
        print("🔍 [BackendVitalsManager] Fetching health metrics...")
        
        // For now, we'll rely on the dashboard data
        refreshDashboard()
    }
    
    func getMetrics(for metricType: String) -> [HealthMetric] {
        // Return empty array for now - this method was used in the old system
        // The new system uses dashboardData instead
        return []
    }
    
    // MARK: - Additional Sync Methods for UI Compatibility
    func forceFullSync() {
        print("🔄 [BackendVitalsManager] Force full sync requested")
        performInitialSync()
    }
    
    func triggerManualSync() {
        print("🔄 [BackendVitalsManager] Manual sync triggered")
        performIncrementalSync()
    }
    
    func forceHealthKitSync() {
        print("🔄 [BackendVitalsManager] Force HealthKit sync (bypassing backend checks)")
        syncManager.performLast24HoursSync()
    }
    
    func refreshDataFromBackend() {
        print("🔄 [BackendVitalsManager] Refreshing data from backend")
        refreshDashboard()
    }
    
    func forceClearSyncState() {
        print("🔄 [BackendVitalsManager] Clearing sync state")
        // Clear any cached sync state
        lastDashboardRefresh = nil
        dashboardData = nil
        refreshDashboard()
    }
    
    // MARK: - Cleanup
    deinit {
        syncTimer?.invalidate()
        NotificationCenter.default.removeObserver(self)
    }
}

 