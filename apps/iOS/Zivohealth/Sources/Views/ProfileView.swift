import SwiftUI

struct ProfileView: View {
    @State private var showingSignOutAlert = false
    @State private var showingDeletionCancelledAlert = false
    @State private var deletionCancelledMessage = ""
    @State private var showingDeleteAccountAlert = false
    @State private var showingDeleteSuccess = false
    
    // Header data
    @State private var headerName: String = ""
    @State private var headerPhone: String = ""
    @State private var headerEmail: String = ""
    
    var body: some View {
        NavigationView {
            GeometryReader { geometry in
                VStack(spacing: 0) {
                    // Reserve space below the overlay header so list starts after it
                    Color.clear.frame(height: 220)

                    // Main profile list content (unchanged functionality)
                    List {
                        // Primary options (no cards)
                        NavigationLink(destination: EditProfileView()) {
                            navRow(title: "Edit profile", systemImage: "person.fill", showChevron: false)
                        }
                        .hideListSeparatorIfAvailable()
                        NavigationLink(destination: NotificationsSettingsView()) {
                            navRow(title: "Notifications", systemImage: "bell.fill", showChevron: false)
                        }
                        .hideListSeparatorIfAvailable()
                        NavigationLink(destination: ConnectedDevicesView()) {
                            navRow(title: "Connected devices", systemImage: "display", showChevron: false)
                        }
                        .hideListSeparatorIfAvailable()
                        Button {
                            showingDeleteAccountAlert = true
                        } label: {
                            navRow(title: "Delete account", systemImage: "trash.fill", showChevron: false)
                        }
                        .hideListSeparatorIfAvailable()

                        // Secondary options
                        Button {
                            MailOpener.open(to: "contactus@zivohealth.ai")
                        } label: {
                            navRow(title: "Contact Us", systemImage: "questionmark.circle.fill", showChevron: false)
                        }
                        .hideListSeparatorIfAvailable()
                        NavigationLink(destination: AboutZivoView()) {
                            navRow(title: "About Zivo", systemImage: "info.circle.fill", showChevron: false)
                        }
                        .hideListSeparatorIfAvailable()

                        // Actions
                        Button {
                            NetworkService.shared.clearAuthToken()
                            NetworkService.shared.handleRoleChange()
                        } label: {
                            actionRow(title: "Refresh Authentication", systemImage: "arrow.clockwise")
                        }
                        .hideListSeparatorIfAvailable()
                        Button(role: .destructive) { showingSignOutAlert = true } label: {
                            actionRow(title: "Logout", systemImage: "arrowshape.turn.up.left")
                        }
                        .hideListSeparatorIfAvailable()
                    }
                    .listStyle(.plain)
                    .hideListSeparatorIfAvailable()
                    .scrollContentBackgroundHiddenIfAvailable()
                    .listRowBackground(Color.white)
                    .background(Color.white)
                    .environment(\.defaultMinListRowHeight, 32)
                }
                // Overlay the full-width header like AppointmentsView
                .overlay(alignment: .top) {
                    profileHeader(topInset: geometry.safeAreaInsets.top)
                }
                .ignoresSafeArea(.container, edges: .top)
            }
            .navigationTitle("")
            .navigationBarTitleDisplayMode(.inline)
            .navigationBarHidden(true)
            .task { await loadHeaderData() }
        .alert("Delete Account?", isPresented: $showingDeleteAccountAlert) {
            Button("No", role: .cancel) { }
            Button("Yes", role: .destructive) {
                Task {
                    do {
                        try await NetworkService.shared.scheduleAccountDeletion()
                        showingDeleteSuccess = true
                    } catch {
                        print("Failed to schedule account deletion: \(error)")
                    }
                }
            }
        } message: {
            let until = Date().addingTimeInterval(7 * 24 * 60 * 60)
            Text("Your account will be deactivated for 7 days and scheduled for deletion on \(until.formatted(date: .abbreviated, time: .omitted)). You can reactivate by signing in again before then.")
        }
        .alert("Account scheduled for deletion", isPresented: $showingDeleteSuccess) {
            Button("OK") {
                NetworkService.shared.clearAllTokens()
                NetworkService.shared.handleRoleChange()
            }
        } message: {
            Text("We have deactivated your account for 7 days. You can reactivate by logging back in before the scheduled deletion date.")
        }
            .alert("Sign Out", isPresented: $showingSignOutAlert) {
                Button("Cancel", role: .cancel) { }
                Button("Sign Out", role: .destructive) {
                    NetworkService.shared.clearAllTokens()
                }
                    } message: {
                        Text("This will sign you out of your account. You will need to log in again.")
                    }
                    .alert("Account Restored", isPresented: $showingDeletionCancelledAlert) {
                        Button("OK") { }
                    } message: {
                        Text(deletionCancelledMessage)
                    }
                }
                .onReceive(NotificationCenter.default.publisher(for: .deletionCancelled)) { notification in
                    if let message = notification.userInfo?["message"] as? String {
                        deletionCancelledMessage = message
                        showingDeletionCancelledAlert = true
                    }
                }
            }
    
    // MARK: - Header
    private var brandRedGradient: Gradient {
        // Left-to-right gradient with darker left side
        Gradient(colors: [
            Color.zivoRed,                 // darker (left)
            Color.zivoRed.opacity(0.7)     // lighter (right)
        ])
    }
    private func profileHeader(topInset: CGFloat) -> some View {
        VStack(spacing: 0) {
            // Top spacer for status bar
            Color.clear
                .frame(height: topInset)
            
            // Card content
            ZStack(alignment: .bottomLeading) {
                LinearGradient(gradient: brandRedGradient, startPoint: .leading, endPoint: .trailing)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                VStack(alignment: .leading, spacing: 6) {
                    // Keep existing content (name/phone/email) but with header style
                    Text("Hey \(headerName.isEmpty ? "there" : headerName)!")
                        .font(.title3).bold()
                        .foregroundColor(.white)
                    if !headerPhone.isEmpty {
                        Text(headerPhone)
                            .font(.subheadline)
                            .foregroundColor(.white)
                    }
                    if !headerEmail.isEmpty {
                        Text(headerEmail)
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.95))
                    }
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 20)
            }
            .frame(height: 140)
            .cornerRadius(20)
            .padding(.horizontal, 16)
            .padding(.top, 8)
        }
        .frame(height: 140 + topInset + 8)
        .ignoresSafeArea(.container, edges: .top)
    }
    
    // MARK: - Rows
    private func iconBadge(systemImage: String) -> some View {
        Image(systemName: systemImage)
            .font(.system(size: 14, weight: .semibold))
            .foregroundColor(.white)
            .frame(width: 24, height: 24)
            .background(
                Circle().fill(
                    LinearGradient(gradient: brandRedGradient, startPoint: .leading, endPoint: .trailing)
                )
            )
    }
    
    private func navRow(title: String, systemImage: String, textColor: Color? = nil, showChevron: Bool = true) -> some View {
        HStack(spacing: 12) {
            iconBadge(systemImage: systemImage)
            Text(title)
                .foregroundColor(textColor ?? .primary)
            Spacer()
            if showChevron {
                Image(systemName: "chevron.right").foregroundColor(.gray)
            }
        }
        .padding(.vertical, 6)
    }
    
    private func actionRow(title: String, systemImage: String, titleColor: Color? = nil) -> some View {
        HStack(spacing: 12) {
            iconBadge(systemImage: systemImage)
            Text(title)
                .foregroundColor(titleColor ?? .primary)
            Spacer()
        }
        .padding(.vertical, 6)
    }
    
    // MARK: - Data
    private func loadHeaderData() async {
        do {
            let profile = try await NetworkService.shared.fetchCombinedProfile()
            await MainActor.run {
                let first = profile.basic.first_name.trimmingCharacters(in: .whitespacesAndNewlines)
                if !first.isEmpty {
                    headerName = first
                } else {
                    let full = profile.basic.full_name.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !full.isEmpty {
                        headerName = full.split(separator: " ").map(String.init).first ?? ""
                    } else {
                        headerName = ""
                    }
                }
                headerPhone = profile.basic.phone_number
                headerEmail = profile.basic.email
            }
        } catch {
            // Fallback to any cached values we have
            await MainActor.run {
                if headerEmail.isEmpty { headerEmail = NetworkService.shared.currentUserEmail ?? "" }
                if headerName.isEmpty {
                    let full = NetworkService.shared.currentUserFullName ?? ""
                    headerName = full.split(separator: " ").map(String.init).first ?? ""
                }
            }
        }
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

// MARK: - Helpers
enum MailOpener {
    static func open(to email: String, subject: String? = nil, body: String? = nil) {
        var components = URLComponents()
        components.scheme = "mailto"
        components.path = email
        var queryItems: [URLQueryItem] = []
        if let subject = subject { queryItems.append(URLQueryItem(name: "subject", value: subject)) }
        if let body = body { queryItems.append(URLQueryItem(name: "body", value: body)) }
        components.queryItems = queryItems.isEmpty ? nil : queryItems
        guard let url = components.url else { return }
        UIApplication.shared.open(url)
    }
}

#Preview {
    ProfileView()
}
