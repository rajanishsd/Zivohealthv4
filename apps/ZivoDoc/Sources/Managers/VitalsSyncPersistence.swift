import Foundation

class VitalsSyncPersistence {
    
    // MARK: - Keys
    
    private enum Keys {
        static let resumableSyncState = "VitalsResumableSyncState"
        static let syncProgress = "VitalsSyncProgressState"
    }
    
    // MARK: - Resumable Sync State
    
    struct ResumableSyncState: Codable {
        let pendingSubmissions: [VitalDataSubmission]
        let completedChunks: Int
        let syncStartDate: Date?
        let syncEndDate: Date?
        let syncType: String
        let lastSaveTime: Date
    }
    
    func saveResumableState(
        pendingSubmissions: [VitalDataSubmission],
        completedChunks: Int,
        syncStartDate: Date?,
        syncEndDate: Date?,
        syncType: SyncType
    ) {
        let state = ResumableSyncState(
            pendingSubmissions: pendingSubmissions,
            completedChunks: completedChunks,
            syncStartDate: syncStartDate,
            syncEndDate: syncEndDate,
            syncType: syncType.rawValue,
            lastSaveTime: Date()
        )
        
        if let encoded = try? JSONEncoder().encode(state) {
            UserDefaults.standard.set(encoded, forKey: Keys.resumableSyncState)
            print("💾 [VitalsSyncPersistence] Saved resumable sync state: \(pendingSubmissions.count) pending, \(completedChunks) completed")
        }
    }
    
    func loadResumableState() -> ResumableSyncState? {
        guard let data = UserDefaults.standard.data(forKey: Keys.resumableSyncState),
              let state = try? JSONDecoder().decode(ResumableSyncState.self, from: data) else {
            return nil
        }
        
        // Only restore if state was saved within the last 24 hours
        let timeSinceLastSave = Date().timeIntervalSince(state.lastSaveTime)
        guard timeSinceLastSave < 86400 else { // 24 hours
            clearResumableState()
            return nil
        }
        
        print("📱 [VitalsSyncPersistence] Loaded resumable sync state: \(state.pendingSubmissions.count) pending, \(state.completedChunks) completed")
        return state
    }
    
    func clearResumableState() {
        UserDefaults.standard.removeObject(forKey: Keys.resumableSyncState)
        print("🗑️ [VitalsSyncPersistence] Cleared resumable sync state")
    }
    
    // MARK: - Last Sync Timestamps
    
    func saveLastSyncTimestamp(_ timestamp: Date, for syncType: SyncType) {
        let key = "LastSync_\(syncType.rawValue)"
        UserDefaults.standard.set(timestamp, forKey: key)
        print("💾 [VitalsSyncPersistence] Saved last sync timestamp for \(syncType.rawValue): \(timestamp)")
    }
    
    func getLastSyncTimestamp(for syncType: SyncType) -> Date? {
        let key = "LastSync_\(syncType.rawValue)"
        return UserDefaults.standard.object(forKey: key) as? Date
    }
    
    // MARK: - Sync Cooldown
    
    func saveLastSyncTime(_ time: Date) {
        UserDefaults.standard.set(time, forKey: "LastSyncTime")
    }
    
    func getLastSyncTime() -> Date? {
        return UserDefaults.standard.object(forKey: "LastSyncTime") as? Date
    }
    
    func isSyncOnCooldown(cooldownInterval: TimeInterval) -> Bool {
        guard let lastSync = getLastSyncTime() else { return false }
        return Date().timeIntervalSince(lastSync) < cooldownInterval
    }
    
    // MARK: - Utility Methods
    
    func clearAllSyncData() {
        clearResumableState()
        UserDefaults.standard.removeObject(forKey: Keys.syncProgress)
        UserDefaults.standard.removeObject(forKey: "LastSyncTime")
        
        // Clear all sync type timestamps
        for syncType in SyncType.allCases {
            let key = "LastSync_\(syncType.rawValue)"
            UserDefaults.standard.removeObject(forKey: key)
        }
        
        print("🗑️ [VitalsSyncPersistence] Cleared all sync data")
    }
} 