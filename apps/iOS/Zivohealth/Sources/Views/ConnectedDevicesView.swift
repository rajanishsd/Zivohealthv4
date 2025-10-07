import SwiftUI
import HealthKitUI
import HealthKit

struct ConnectedDevicesView: View {
    @State private var healthKitFeatureEnabled = true
    @State private var healthKitConnected = false
    @State private var isLoading = true
    @State private var hkTrigger = false
    @StateObject private var healthKitAuth = HealthKitAuthorizationService.shared
    
    var body: some View {
        List {
            if healthKitFeatureEnabled {
                HStack(spacing: 12) {
                    iconBadge(systemImage: "heart.fill")
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Apple Health (HealthKit)")
                            .font(.body)
                        Text(healthKitConnected ? "Connected" : "Not connected")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                    Toggle("", isOn: $healthKitConnected)
                        .labelsHidden()
                }
                .padding(.vertical, 6)
                .hideListSeparatorIfAvailable()
            }
        }
        .listStyle(.plain)
        .hideListSeparatorIfAvailable()
        .scrollContentBackgroundHiddenIfAvailable()
        .listRowBackground(Color.white)
        .background(Color.white.ignoresSafeArea())
        .environment(\.defaultMinListRowHeight, 32)
        .navigationTitle("Connected Devices")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await loadInitialState()
        }
        .onChange(of: healthKitConnected) { newValue in
            if newValue {
                if #available(iOS 17.0, *) {
                    hkTrigger.toggle()
                } else {
                    // Revert and inform user on older OS versions
                    healthKitConnected = false
                    healthKitAuth.showAlert("Health access requires iOS 17 or later.")
                }
            } else {
                Task { await updateBackendConnection(false) }
            }
        }
        .healthDataAccessRequestIfAvailable(
            store: HKHealthStore(),
            shareTypes: [],
            readTypes: HealthKitAuthorizationService.allReadTypes(),
            trigger: hkTrigger
        ) { result in
            switch result {
            case .success:
                healthKitConnected = true
                Task { await updateBackendConnection(true) }
            case .failure:
                healthKitConnected = false
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
            // Refresh authorization status when app becomes active (user returns from Settings)
            healthKitAuth.refreshAuthorizationStatus()
            Task {
                await refreshHealthKitStatus()
            }
        }
        .background(healthKitAuth.alertView())
    }
    
    // MARK: - Initialization
    private func loadInitialState() async {
        isLoading = true
        
        do {
            let cfg = try await NetworkService.shared.fetchDevicesConfig()
            healthKitFeatureEnabled = cfg.healthkit_enabled
        } catch {
            healthKitFeatureEnabled = true
        }
        
        do {
            let status = try await NetworkService.shared.getDeviceStatus(provider: "healthkit")
            healthKitConnected = status.is_connected
        } catch {
            // Keep default
        }
        
        isLoading = false
    }
    
    // MARK: - HealthKit Connection
    
    private func updateBackendConnection(_ isConnected: Bool) async {
        do {
            _ = try await NetworkService.shared.setDeviceStatus(provider: "healthkit", isConnected: isConnected)
        } catch {
            healthKitAuth.showAlert("Failed to update connection status: \(error.localizedDescription)")
            healthKitConnected.toggle()
        }
    }
    
    // MARK: - Refresh Methods
    private func refreshHealthKitStatus() async {
        print("🔄 Refreshing HealthKit status...")
        
        // First check current status without requesting authorization
        healthKitAuth.checkAuthorizationStatus()
        
        // Check if HealthKit is now authorized after user returned from Settings
        let isAuthorized = await healthKitAuth.requestAuthorization()
        
        print("🔄 HealthKit authorized: \(isAuthorized)")
        print("🔄 Current UI state: \(healthKitConnected)")
        
        // Only auto-connect if authorized; do not auto-disconnect when unauthorized
        if isAuthorized && !healthKitConnected {
            print("🔄 Updating UI to connected state")
            healthKitConnected = true
            await updateBackendConnection(true)
        } else if !isAuthorized && healthKitConnected {
            print("🔄 HealthKit no longer authorized, updating UI to disconnected state")
            healthKitConnected = false
            await updateBackendConnection(false)
        }
    }
    
    // MARK: - UI Components
    private func iconBadge(systemImage: String) -> some View {
        Image(systemName: systemImage)
            .font(.system(size: 14, weight: .semibold))
            .foregroundColor(.white)
            .frame(width: 24, height: 24)
            .background(
                Circle().fill(
                    LinearGradient(
                        gradient: Gradient(colors: [Color.zivoRed, Color.zivoRed.opacity(0.7)]),
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
            )
    }
}

// MARK: - Backwards compatibility helpers
private extension View {
    @ViewBuilder
    func scrollContentBackgroundHiddenIfAvailable() -> some View {
        if #available(iOS 16.0, *) {
            self.scrollContentBackground(.hidden)
        } else {
            self
        }
    }

    @ViewBuilder
    func hideListSeparatorIfAvailable() -> some View {
        if #available(iOS 15.0, *) {
            self.listRowSeparator(.hidden)
        } else {
            self
        }
    }
}

// Compatibility wrapper for HealthKitUI API (iOS 17+)
private extension View {
    @ViewBuilder
    func healthDataAccessRequestIfAvailable(
        store: HKHealthStore,
        shareTypes: Set<HKSampleType>,
        readTypes: Set<HKObjectType>,
        trigger: Bool,
        completion: @escaping (Result<Bool, Error>) -> Void
    ) -> some View {
        if #available(iOS 17.0, *) {
            self.healthDataAccessRequest(
                store: store,
                shareTypes: shareTypes,
                readTypes: readTypes,
                trigger: trigger,
                completion: completion
            )
        } else {
            self
        }
    }
}

#Preview {
    NavigationView {
        ConnectedDevicesView()
    }
}
