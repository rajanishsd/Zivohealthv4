import Foundation
import Network
import Combine

class VitalsNetworkMonitor: ObservableObject {
    private let networkMonitor = NWPathMonitor()
    private let networkQueue = DispatchQueue(label: "NetworkMonitor")
    
    @Published var isNetworkAvailable = true
    private var wasOffline = false
    
    // Network failure retry mechanism
    private var retryTimer: Timer?
    private var retryCount = 0
    private let maxRetryAttempts = 3
    private var lastFailedSyncReason: String?
    
    // Callbacks
    var onNetworkRestored: (() -> Void)?
    var onNetworkLost: (() -> Void)?
    var onRetrySync: (() -> Void)?
    
    init() {
        setupNetworkMonitoring()
    }
    
    deinit {
        networkMonitor.cancel()
        retryTimer?.invalidate()
    }
    
    // MARK: - Network Monitoring
    
    private func setupNetworkMonitoring() {
        networkMonitor.pathUpdateHandler = { [weak self] path in
            DispatchQueue.main.async {
                let wasAvailable = self?.isNetworkAvailable ?? true
                self?.isNetworkAvailable = path.status == .satisfied
                
                print("🌐 [VitalsNetworkMonitor] Network status changed: \(path.status)")
                
                // If network just came back online and we were offline
                if !wasAvailable && self?.isNetworkAvailable == true {
                    print("🟢 [VitalsNetworkMonitor] Network connectivity restored")
                    self?.handleNetworkRestored()
                } else if wasAvailable && self?.isNetworkAvailable == false {
                    print("🔴 [VitalsNetworkMonitor] Network connectivity lost")
                    self?.handleNetworkLost()
                }
            }
        }
        networkMonitor.start(queue: networkQueue)
    }
    
    private func handleNetworkRestored() {
        wasOffline = false
        retryCount = 0
        
        // Cancel any existing retry timer
        retryTimer?.invalidate()
        retryTimer = nil
        
        // If we had a failed sync due to network issues, retry it
        if let failedReason = lastFailedSyncReason {
            print("🔄 [VitalsNetworkMonitor] Retrying sync after network restoration: \(failedReason)")
            lastFailedSyncReason = nil
            
            // Wait a moment for network to stabilize, then retry
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                self.onRetrySync?()
            }
        } else {
            // Check if there's new data to sync since we've been offline
            print("🔄 [VitalsNetworkMonitor] Network restored - checking for new data to sync")
            DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) {
                self.onNetworkRestored?()
            }
        }
    }
    
    private func handleNetworkLost() {
        wasOffline = true
        onNetworkLost?()
        
        print("⚠️ [VitalsNetworkMonitor] Network lost - will retry when restored")
    }
    
    // MARK: - Error Handling
    
    func handleSyncError(_ error: Error, context: String, onRetryScheduled: @escaping (String) -> Void, onRetryFailed: @escaping (String) -> Void) {
        print("❌ [VitalsNetworkMonitor] Sync error in \(context): \(error)")
        
        let isNetworkError = isNetworkRelatedError(error)
        
        if isNetworkError {
            lastFailedSyncReason = context
            
            if isNetworkAvailable && retryCount < maxRetryAttempts {
                // Network appears available but request failed - schedule retry
                retryCount += 1
                let retryDelay = Double(retryCount) * 5.0 // Exponential backoff: 5s, 10s, 15s
                
                print("🔄 [VitalsNetworkMonitor] Scheduling retry \(retryCount)/\(maxRetryAttempts) in \(retryDelay)s")
                
                retryTimer = Timer.scheduledTimer(withTimeInterval: retryDelay, repeats: false) { [weak self] _ in
                    self?.onRetrySync?()
                }
                
                onRetryScheduled("Network error - retrying in \(Int(retryDelay))s...")
            } else if !isNetworkAvailable {
                // Network is definitely unavailable - wait for restoration
                onRetryScheduled("No network connection - will retry when restored")
            } else {
                // Max retries reached
                onRetryFailed("Sync failed after \(maxRetryAttempts) attempts: \(error.localizedDescription)")
                lastFailedSyncReason = nil
                retryCount = 0
            }
        } else {
            // Non-network error - don't retry automatically
            onRetryFailed("Sync failed: \(error.localizedDescription)")
            lastFailedSyncReason = nil
            retryCount = 0
        }
    }
    
    private func isNetworkRelatedError(_ error: Error) -> Bool {
        if let urlError = error as? URLError {
            switch urlError.code {
            case .notConnectedToInternet, .networkConnectionLost, .timedOut, 
                 .cannotConnectToHost, .cannotFindHost, .dnsLookupFailed:
                return true
            default:
                return false
            }
        }
        
        // Check for NSError with network-related domains
        if let nsError = error as NSError? {
            if nsError.domain == NSURLErrorDomain {
                return true
            }
        }
        
        // Check error description for network-related keywords
        let errorDescription = error.localizedDescription.lowercased()
        return errorDescription.contains("network") || 
               errorDescription.contains("connection") || 
               errorDescription.contains("timeout") ||
               errorDescription.contains("offline") ||
               errorDescription.contains("unreachable")
    }
    
    // MARK: - Public Methods
    
    func hasFailedSyncPendingRetry() -> Bool {
        return lastFailedSyncReason != nil
    }
    
    func manualRetrySync() {
        guard hasFailedSyncPendingRetry() else {
            print("⚠️ [VitalsNetworkMonitor] No failed sync to retry")
            return
        }
        
        print("🔄 [VitalsNetworkMonitor] Manual retry requested")
        retryTimer?.invalidate()
        retryTimer = nil
        onRetrySync?()
    }
    
    func clearRetryState() {
        lastFailedSyncReason = nil
        retryCount = 0
        retryTimer?.invalidate()
        retryTimer = nil
    }
} 