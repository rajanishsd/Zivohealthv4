import SwiftUI

struct SyncProgressView: View {
    @ObservedObject var healthKitManager: BackendVitalsManager
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Network Status Banner
            if !healthKitManager.isNetworkAvailable || healthKitManager.hasFailedSyncPendingRetry {
                NetworkStatusBanner(
                    isNetworkAvailable: healthKitManager.isNetworkAvailable,
                    hasFailedSync: healthKitManager.hasFailedSyncPendingRetry,
                    onRetry: {
                        healthKitManager.retryFailedSync()
                    }
                )
            }
            
            // Sync Progress Section
            if healthKitManager.isSyncing || healthKitManager.syncProgress > 0.0 {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("Progress")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        
                        Spacer()
                        
                        let displayProgress = healthKitManager.totalDataPoints > 0 ? 
                            Double(healthKitManager.syncedDataPoints) / Double(healthKitManager.totalDataPoints) : healthKitManager.syncProgress
                        Text("\(Int(displayProgress * 100))%")
                            .font(.headline)
                            .foregroundColor(.primary)
                    }
                    
                    // Progress Bar (based on data points)
                    ZStack(alignment: .leading) {
                        Rectangle()
                            .frame(height: 8)
                            .foregroundColor(Color.gray.opacity(0.3))
                            .cornerRadius(4)
                        
                        let dataBasedProgress = healthKitManager.totalDataPoints > 0 ? 
                            Double(healthKitManager.syncedDataPoints) / Double(healthKitManager.totalDataPoints) : healthKitManager.syncProgress
                        
                        Rectangle()
                            .frame(width: CGFloat(dataBasedProgress) * (UIScreen.main.bounds.width - 64), height: 8)
                            .foregroundColor(healthKitManager.isNetworkAvailable ? .blue : .orange)
                            .cornerRadius(4)
                            .animation(.easeInOut(duration: 0.5), value: dataBasedProgress)
                    }
                }
                .transition(.slide)
            }
            
            // Status Message
            if !healthKitManager.syncMessage.isEmpty {
                HStack {
                    if healthKitManager.isSyncing {
                        ProgressView()
                            .scaleEffect(0.8)
                            .progressViewStyle(CircularProgressViewStyle(tint: healthKitManager.isNetworkAvailable ? .blue : .orange))
                    } else if healthKitManager.hasFailedSyncPendingRetry {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.orange)
                    } else if !healthKitManager.isNetworkAvailable {
                        Image(systemName: "wifi.slash")
                            .foregroundColor(.red)
                    }
                    
                    Text(healthKitManager.syncMessage)
                        .font(.subheadline)
                        .foregroundColor(healthKitManager.isSyncing ? .primary : .secondary)
                        .multilineTextAlignment(.leading)
                    
                    Spacer()
                }
                .transition(.opacity)
            }
            
            // Error Message with Retry Option
            if let errorMessage = healthKitManager.errorMessage, !errorMessage.isEmpty {
                HStack {
                    Image(systemName: "exclamationmark.circle.fill")
                        .foregroundColor(.red)
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text(errorMessage)
                            .font(.subheadline)
                            .foregroundColor(.red)
                            .multilineTextAlignment(.leading)
                        
                        if healthKitManager.hasFailedSyncPendingRetry {
                            Button("Retry Now") {
                                healthKitManager.retryFailedSync()
                            }
                        .font(.caption)
                            .foregroundColor(.blue)
                        }
                    }
                    
                    Spacer()
                }
                .padding(.vertical, 4)
                .transition(.opacity)
            }
            
            // Data Points Summary
            if healthKitManager.totalDataPoints > 0 {
                VStack(spacing: 8) {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Data Points")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Text("\(healthKitManager.syncedDataPoints) / \(healthKitManager.totalDataPoints)")
                                .font(.headline)
                                .foregroundColor(healthKitManager.syncedDataPoints == healthKitManager.totalDataPoints ? .green : .primary)
                        }
                        
                        Spacer()
                        
                        VStack(alignment: .trailing, spacing: 2) {
                            Text("Progress")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            let dataProgress = healthKitManager.totalDataPoints > 0 ? 
                                Double(healthKitManager.syncedDataPoints) / Double(healthKitManager.totalDataPoints) : 0.0
                            Text("\(Int(dataProgress * 100))%")
                                .font(.headline)
                                .foregroundColor(healthKitManager.isNetworkAvailable ? .blue : .orange)
                        }
                    }
                    
                    // Data points progress bar
                    ZStack(alignment: .leading) {
                        Rectangle()
                            .frame(height: 6)
                            .foregroundColor(Color.gray.opacity(0.2))
                            .cornerRadius(3)
                        
                        let dataProgress = healthKitManager.totalDataPoints > 0 ? 
                            Double(healthKitManager.syncedDataPoints) / Double(healthKitManager.totalDataPoints) : 0.0
                        
                            Rectangle()
                            .frame(width: CGFloat(dataProgress) * (UIScreen.main.bounds.width - 64), height: 6)
                            .foregroundColor(healthKitManager.syncedDataPoints == healthKitManager.totalDataPoints ? .green : (healthKitManager.isNetworkAvailable ? .blue : .orange))
                            .cornerRadius(3)
                                .animation(.easeInOut(duration: 0.3), value: dataProgress)
                    }
                }
                .padding(.vertical, 8)
                .transition(.slide)
            }
            
            // Current Metric Being Synced
            if !healthKitManager.currentMetricBeingSynced.isEmpty && healthKitManager.isSyncing {
                        HStack {
                    Text("Current:")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Text(healthKitManager.currentMetricBeingSynced)
                        .font(.caption)
                        .foregroundColor(.primary)
                    
                    Spacer()
                }
                .transition(.opacity)
            }
        }
        .padding()
        .background(Color(UIColor.secondarySystemBackground))
        .cornerRadius(12)
        .animation(.easeInOut(duration: 0.3), value: healthKitManager.isSyncing)
        .animation(.easeInOut(duration: 0.3), value: healthKitManager.isNetworkAvailable)
        .animation(.easeInOut(duration: 0.3), value: healthKitManager.hasFailedSyncPendingRetry)
    }
}

struct NetworkStatusBanner: View {
    let isNetworkAvailable: Bool
    let hasFailedSync: Bool
    let onRetry: () -> Void
    
    var body: some View {
        HStack {
            Image(systemName: iconName)
                .foregroundColor(iconColor)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(statusTitle)
                    .font(.headline)
                    .foregroundColor(iconColor)
                
                Text(statusMessage)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            if hasFailedSync && isNetworkAvailable {
                Button("Retry") {
                    onRetry()
                }
                .font(.callout)
                .foregroundColor(.white)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color.blue)
                .cornerRadius(8)
            } else if !isNetworkAvailable {
                ProgressView()
                    .scaleEffect(0.7)
                    .progressViewStyle(CircularProgressViewStyle(tint: .orange))
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(backgroundColor)
        .cornerRadius(8)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(borderColor, lineWidth: 1)
        )
    }
    
    private var iconName: String {
        if !isNetworkAvailable {
            return "wifi.slash"
        } else if hasFailedSync {
            return "exclamationmark.triangle.fill"
        } else {
            return "wifi"
        }
    }
    
    private var iconColor: Color {
        if !isNetworkAvailable {
            return .red
        } else if hasFailedSync {
            return .orange
        } else {
            return .green
        }
    }
    
    private var statusTitle: String {
        if !isNetworkAvailable {
            return "No Internet Connection"
        } else if hasFailedSync {
            return "Sync Failed"
        } else {
            return "Connected"
        }
    }
    
    private var statusMessage: String {
        if !isNetworkAvailable {
            return "Waiting for connection to resume sync"
        } else if hasFailedSync {
            return "Network error occurred - tap retry to continue"
        } else {
            return "Network connection active"
        }
    }
    
    private var backgroundColor: Color {
        if !isNetworkAvailable {
            return Color.red.opacity(0.1)
        } else if hasFailedSync {
            return Color.orange.opacity(0.1)
        } else {
            return Color.green.opacity(0.1)
        }
    }
    
    private var borderColor: Color {
        if !isNetworkAvailable {
            return Color.red.opacity(0.3)
        } else if hasFailedSync {
            return Color.orange.opacity(0.3)
        } else {
            return Color.green.opacity(0.3)
        }
    }
}

#Preview {
    VStack {
        SyncProgressView(healthKitManager: BackendVitalsManager.shared)
    }
    .padding()
} 