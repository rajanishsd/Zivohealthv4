import Foundation
import Combine
import UIKit

class VitalsSyncProgress: ObservableObject {
    // Sync progress tracking
    @Published var isSyncing = false
    @Published var syncProgress: Double = 0.0
    @Published var syncMessage = "Ready to sync"
    @Published var totalDataPoints: Int = 0
    @Published var syncedDataPoints: Int = 0
    @Published var currentMetricBeingSynced: String = ""
    @Published var errorMessage: String?
    
    // Background task support
    private var backgroundTaskId: UIBackgroundTaskIdentifier = .invalid
    
    // MARK: - Progress Management
    
    func startSyncProgress() {
        DispatchQueue.main.async {
            self.isSyncing = true
            self.syncProgress = 0.0
            self.syncMessage = "Starting sync..."
            self.totalDataPoints = 0
            self.syncedDataPoints = 0
            self.currentMetricBeingSynced = ""
            self.errorMessage = nil
        }
        startBackgroundTask()
    }
    
    func updateSyncProgress(current: Int, total: Int, message: String, currentMetric: String = "") {
        DispatchQueue.main.async {
            self.syncedDataPoints = current
            self.totalDataPoints = total
            self.syncProgress = total > 0 ? Double(current) / Double(total) : 0.0
            self.syncMessage = message
            if !currentMetric.isEmpty {
                self.currentMetricBeingSynced = currentMetric
            }
        }
    }
    
    func completeSyncProgress(success: Bool, message: String) {
        DispatchQueue.main.async {
            self.isSyncing = false
            self.syncProgress = success ? 1.0 : 0.0
            self.syncMessage = message
            if !success {
                self.errorMessage = message
            } else {
                self.errorMessage = nil
            }
        }
        endBackgroundTask()
    }
    
    func clearSyncProgress() {
        DispatchQueue.main.async {
            self.isSyncing = false
            self.syncProgress = 0.0
            self.syncMessage = "Ready to sync"
            self.totalDataPoints = 0
            self.syncedDataPoints = 0
            self.currentMetricBeingSynced = ""
            self.errorMessage = nil
        }
    }
    
    // MARK: - Background Task Management
    
    private func startBackgroundTask() {
        endBackgroundTask() // End any existing task first
        
        backgroundTaskId = UIApplication.shared.beginBackgroundTask(withName: "VitalsSync") {
            print("⏰ [VitalsSyncProgress] Background task expired")
            self.endBackgroundTask()
        }
        
        print("🔄 [VitalsSyncProgress] Started background task: \(backgroundTaskId.rawValue)")
    }
    
    private func endBackgroundTask() {
        if backgroundTaskId != .invalid {
            print("✅ [VitalsSyncProgress] Ending background task: \(backgroundTaskId.rawValue)")
            UIApplication.shared.endBackgroundTask(backgroundTaskId)
            backgroundTaskId = .invalid
        }
    }
    
    // MARK: - State Persistence
    
    func saveProgressState(syncType: SyncType) {
        let state = SyncProgressState(
            isSyncing: isSyncing,
            syncProgress: syncProgress,
            syncMessage: syncMessage,
            totalDataPoints: totalDataPoints,
            syncedDataPoints: syncedDataPoints,
            currentMetricBeingSynced: currentMetricBeingSynced,
            syncStartTime: Date(),
            syncType: syncType.rawValue
        )
        
        if let encoded = try? JSONEncoder().encode(state) {
            UserDefaults.standard.set(encoded, forKey: "VitalsSyncProgressState")
            print("💾 [VitalsSyncProgress] Saved progress state")
        }
    }
    
    func restoreProgressState() -> SyncProgressState? {
        guard let data = UserDefaults.standard.data(forKey: "VitalsSyncProgressState"),
              let state = try? JSONDecoder().decode(SyncProgressState.self, from: data) else {
            return nil
        }
        
        // Only restore if sync was started within the last hour
        let timeSinceSync = Date().timeIntervalSince(state.syncStartTime)
        guard timeSinceSync < 3600 else {
            clearPersistedProgressState()
            return nil
        }
        
        DispatchQueue.main.async {
            self.isSyncing = state.isSyncing
            self.syncProgress = state.syncProgress
            self.syncMessage = state.syncMessage
            self.totalDataPoints = state.totalDataPoints
            self.syncedDataPoints = state.syncedDataPoints
            self.currentMetricBeingSynced = state.currentMetricBeingSynced
        }
        
        print("📱 [VitalsSyncProgress] Restored progress state: \(state.syncMessage)")
        return state
    }
    
    func clearPersistedProgressState() {
        UserDefaults.standard.removeObject(forKey: "VitalsSyncProgressState")
    }
} 