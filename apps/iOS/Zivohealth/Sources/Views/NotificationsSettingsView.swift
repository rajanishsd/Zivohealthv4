import SwiftUI
import UserNotifications
import UIKit

struct NotificationsSettingsView: View {
    @State private var isAuthorized: Bool = false
    @State private var isEnabled: Bool = false
    // Toggle mirrors iOS permission; backend stores preference equal to current iOS state
    @State private var showingAlert: Bool = false

    var body: some View {
        List {
            HStack(spacing: 12) {
                iconBadge(systemImage: "bell.fill")
                VStack(alignment: .leading, spacing: 2) {
                    Text("Notifications")
                        .font(.body)
                    Text(isAuthorized ? "Allowed in iOS Settings" : "Disabled in iOS Settings")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                Spacer()
                Toggle("", isOn: $isEnabled)
                    .labelsHidden()
            }
            .padding(.vertical, 6)
            .hideListSeparatorIfAvailable()

            // Removed inline "Open Notification Settings" link; we open Settings programmatically when needed
        }
        .listStyle(.plain)
        .hideListSeparatorIfAvailable()
        .scrollContentBackgroundHiddenIfAvailable()
        .listRowBackground(Color.white)
        .background(Color.white.ignoresSafeArea())
        .environment(\.defaultMinListRowHeight, 32)
        .navigationTitle("Notifications")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { refreshAuthorizationStatus() }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
            // Inherit current iOS Settings state whenever app returns to foreground
            refreshAuthorizationStatus()
        }
        .onChange(of: isEnabled) { newValue in
            handleToggleChange(newValue)
        }
        .alert("Notifications", isPresented: $showingAlert) {
            Button("Open Settings") { openSystemSettings() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("To change notifications, use iOS Settings → Notifications → Zivohealth")
        }
    }

    private func handleToggleChange(_ newValue: Bool) {
        if newValue {
            // Turning ON: request authorization if not authorized
            if !isAuthorized {
                UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, _ in
                    DispatchQueue.main.async {
                        self.isAuthorized = granted
                        self.isEnabled = granted
                        if !granted { self.showingAlert = true }
                        Task {
                            try? await NetworkService.shared.updateNotificationSettings(enabled: granted)
                        }
                    }
                }
            } else {
                Task {
                    try? await NetworkService.shared.updateNotificationSettings(enabled: true)
                }
            }
        } else {
            // Cannot revoke programmatically; ask user to open Settings
            self.showingAlert = true
            // Reflect the actual OS permission instead of forcing state
            DispatchQueue.main.async {
                self.isEnabled = self.isAuthorized
            }
            Task { try? await NetworkService.shared.updateNotificationSettings(enabled: false) }
        }
    }

    private func refreshAuthorizationStatus() {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            DispatchQueue.main.async {
                let authorized = settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional || settings.authorizationStatus == .ephemeral
                self.isAuthorized = authorized
                // Mirror iOS Settings directly in the toggle
                self.isEnabled = authorized
                // Keep backend in sync with current iOS permission
                Task { try? await NetworkService.shared.updateNotificationSettings(enabled: authorized) }
            }
        }
    }

    private func openSystemSettings() {
        if let url = URL(string: UIApplication.openSettingsURLString) {
            UIApplication.shared.open(url)
        }
    }

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

#Preview {
    NavigationView {
        NotificationsSettingsView()
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


