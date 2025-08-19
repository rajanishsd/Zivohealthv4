import SwiftUI

struct ContentView: View {
    @AppStorage("userMode") private var userMode: UserMode = .patient
    @AppStorage("patientAuthToken") private var patientAuthToken = ""
    @State private var showingRoleSelection = false
    @State private var selectedTab = 0

    var body: some View {
        if (patientAuthToken.isEmpty && userMode == .patient) {
            if #available(iOS 16.0, *) {
                NavigationStack { PatientLoginView { } }
            } else {
                NavigationView { PatientLoginView { } }
            }
        } else if showingRoleSelection {
            // Show only role selection without bottom navigation
            HomeView(onRoleSelected: {
                showingRoleSelection = false
            })
        } else {
            // Show main app with role-based navigation
            if #available(iOS 16.0, *) {
                NavigationStack {
                    TabView(selection: $selectedTab) {
                        // Home/Role Selection Tab
                        MainHomeView(onSwitchRole: {
                            showingRoleSelection = true
                        })
                        .id("home-\(userMode.rawValue)")
                        .tabItem {
                            Label("Home", systemImage: "house.fill")
                        }

                        // Role-specific tabs
                        if userMode == .patient {
                            Health360OverviewView(healthKitManager: BackendVitalsManager.shared)
                            .tabItem {
                                Label("Health 360", systemImage: "heart")
                            }
                            .tag(1)

                            ChatView()
                            .tabItem {
                                Label("Chat", systemImage: "message")
                            }
                            .tag(2)

                            AppointmentsView()
                            .tabItem {
                                Label("Appointments", systemImage: "calendar")
                            }
                            .tag(3)

                            SettingsView()
                            .tabItem {
                                Label("Settings", systemImage: "gear")
                            }
                            .tag(4)
                        } else {
                            // Doctor tabs
                            DoctorDashboardView(onSwitchRole: {
                                showingRoleSelection = true
                            })
                            .tabItem {
                                Label("Dashboard", systemImage: "stethoscope")
                            }
                            .tag(1)

                            AppointmentsView()
                            .tabItem {
                                Label("Appointments", systemImage: "calendar")
                            }
                            .tag(2)

                            SettingsView()
                            .tabItem {
                                Label("Settings", systemImage: "gear")
                            }
                            .tag(3)
                        }
                    }
                    .id(userMode.rawValue) // Force TabView reconstruction when role changes
                    .onReceive(NotificationCenter.default.publisher(for: Notification.Name("SwitchToChatTab"))) { _ in
                        selectedTab = 2 // Chat tab for patients
                    }
                    .navigationDestination(for: String.self) { category in
                        switch category {
                        case "Diabetes Panel":
                            DiabetesPanelView()
                                .navigationBarHidden(true)
                        case "Thyroid Profile":
                            ThyroidProfileView()
                                .navigationBarHidden(true)
                        case "Lipid Profile":
                            LipidProfileView()
                                .navigationBarHidden(true)
                        case "Complete Blood Count":
                            CompleteBloodCountView()
                                .navigationBarHidden(true)
                        case "Liver Function Tests (LFT)":
                            LiverFunctionTestsView()
                                .navigationBarHidden(true)
                        case "Kidney Function Tests (KFT)":
                            KidneyFunctionTestsView()
                                .navigationBarHidden(true)
                        case "Electrolyte Panel":
                            ElectrolytePanelView()
                                .navigationBarHidden(true)
                        case "Infection Markers":
                            InfectionMarkersView()
                                .navigationBarHidden(true)
                        case "Vitamin & Mineral Panel":
                            VitaminMineralPanelView()
                                .navigationBarHidden(true)
                        case "Cardiac Markers":
                            CardiacMarkersView()
                                .navigationBarHidden(true)
                        case "Urine Routine":
                            UrineRoutineView()
                                .navigationBarHidden(true)
                        case "Others":
                            OthersView()
                                .navigationBarHidden(true)
                        default:
                            Text("Coming Soon: \(category)")
                                .navigationTitle(category)
                        }
                    }
                    .onAppear {
                        // Configure tab bar appearance to be solid and prevent transparency
                        let tabBarAppearance = UITabBarAppearance()
                        tabBarAppearance.configureWithOpaqueBackground()
                        tabBarAppearance.backgroundColor = UIColor.systemBackground
                        
                        UITabBar.appearance().standardAppearance = tabBarAppearance
                        UITabBar.appearance().scrollEdgeAppearance = tabBarAppearance
                    }
                }
                .id(userMode.rawValue) // Force NavigationStack reconstruction when role changes
            } else {
                // iOS 15 fallback - keep original NavigationView
            NavigationView {
                TabView(selection: $selectedTab) {
                    // Home/Role Selection Tab
                    MainHomeView(onSwitchRole: {
                        showingRoleSelection = true
                    })
                    .id("home-\(userMode.rawValue)")
                    .tabItem {
                        Label("Home", systemImage: "house.fill")
                    }

                    // Role-specific tabs
                    if userMode == .patient {
                        Health360OverviewView(healthKitManager: BackendVitalsManager.shared)
                        .tabItem {
                            Label("Health 360", systemImage: "heart")
                        }
                        .tag(1)

                        ChatView()
                        .tabItem {
                            Label("Chat", systemImage: "message")
                        }
                        .tag(2)

                        AppointmentsView()
                        .tabItem {
                            Label("Appointments", systemImage: "calendar")
                        }
                        .tag(3)

                        SettingsView()
                        .tabItem {
                            Label("Settings", systemImage: "gear")
                        }
                        .tag(4)
                    } else {
                        // Doctor tabs
                        DoctorDashboardView(onSwitchRole: {
                            showingRoleSelection = true
                        })
                        .tabItem {
                            Label("Dashboard", systemImage: "stethoscope")
                        }
                        .tag(1)

                        AppointmentsView()
                        .tabItem {
                            Label("Appointments", systemImage: "calendar")
                        }
                        .tag(2)

                        SettingsView()
                        .tabItem {
                            Label("Settings", systemImage: "gear")
                        }
                        .tag(3)
                    }
                }
                .id(userMode.rawValue) // Force TabView reconstruction when role changes
                .onReceive(NotificationCenter.default.publisher(for: Notification.Name("SwitchToChatTab"))) { _ in
                    selectedTab = 2 // Chat tab for patients
                }
                .onAppear {
                    // Configure tab bar appearance to be solid and prevent transparency
                    let tabBarAppearance = UITabBarAppearance()
                    tabBarAppearance.configureWithOpaqueBackground()
                    tabBarAppearance.backgroundColor = UIColor.systemBackground
                    
                    UITabBar.appearance().standardAppearance = tabBarAppearance
                    UITabBar.appearance().scrollEdgeAppearance = tabBarAppearance
                }
                .navigationViewStyle(.stack)
            }
            .id(userMode.rawValue) // Force NavigationView reconstruction when role changes
            }
        }
    }
}

// Main home view that shows current role and allows switching
struct MainHomeView: View {
    @AppStorage("userMode") private var userMode: UserMode = .patient
    let onSwitchRole: () -> Void

    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(
                gradient: Gradient(colors: [Color.blue.opacity(0.1), Color.purple.opacity(0.1)]),
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            VStack(spacing: 40) {
                Spacer()

                // App Logo and Title
                VStack(spacing: 16) {
                    Image(systemName: "heart.circle.fill")
                        .font(.system(size: 80))
                        .foregroundColor(.blue)

                    Text("ZivoHealth")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .foregroundColor(.primary)

                    Text("Smart Healthcare Platform")
                        .font(.title3)
                        .foregroundColor(.secondary)
                }

                // Current Role Display
                VStack(spacing: 12) {
                    Text("Current Role")
                        .font(.headline)
                        .foregroundColor(.secondary)

                    HStack {
                        Image(systemName: userMode == .patient ? "person.circle.fill" : "stethoscope.circle.fill")
                            .font(.title)
                            .foregroundColor(.blue)

                        Text(userMode == .patient ? "Patient" : "Doctor")
                            .font(.title2)
                            .fontWeight(.semibold)
                    }
                    .padding()
                    .background(Color.blue.opacity(0.1))
                    .cornerRadius(12)
                }

                // Role-specific welcome message
                VStack(spacing: 8) {
                    if userMode == .patient {
                        Text("Welcome! You can now:")
                            .font(.headline)
                            .foregroundColor(.primary)

                        VStack(alignment: .leading, spacing: 4) {
                            Text("• Chat with AI for health guidance")
                            Text("• Request consultations with doctors")
                            Text("• Track your health metrics")
                            Text("• View your chat history")
                        }
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    } else {
                        Text("Welcome Doctor! You can now:")
                            .font(.headline)
                            .foregroundColor(.primary)

                        VStack(alignment: .leading, spacing: 4) {
                            Text("• Review consultation requests")
                            Text("• Manage patient cases")
                            Text("• Provide medical care")
                            Text("• Update patient records")
                        }
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    }
                }
                .padding()
                .background(Color.gray.opacity(0.1))
                .cornerRadius(12)

                // Quick action based on role
                VStack(spacing: 16) {
                    if userMode == .patient {
                        Text("Get started by exploring the tabs below")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)

                        HStack(spacing: 20) {
                            QuickActionButton(
                                icon: "message.circle.fill",
                                title: "Start Chat",
                                subtitle: "Chat tab"
                            )

                            QuickActionButton(
                                icon: "heart.circle.fill",
                                title: "Health Metrics",
                                subtitle: "Health tab"
                            )
                        }
                    } else {
                        Text("Check your dashboard for consultation requests")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)

                        QuickActionButton(
                            icon: "stethoscope.circle.fill",
                            title: "Dashboard",
                            subtitle: "View requests"
                        )
                    }
                }
                
                // Switch Role Button - Prominent placement
                Button(action: onSwitchRole) {
                    HStack(spacing: 8) {
                        Image(systemName: "arrow.triangle.2.circlepath")
                            .font(.title3)
                        Text("Switch Role")
                            .font(.headline)
                    }
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(
                        LinearGradient(
                            gradient: Gradient(colors: [Color.blue, Color.purple]),
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .cornerRadius(12)
                    .shadow(color: Color.blue.opacity(0.3), radius: 4, x: 0, y: 2)
                }
                .padding(.horizontal, 20)

                Spacer()
            }
            .padding()
        }
        .navigationTitle("ZivoHealth")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button(action: onSwitchRole) {
                    HStack(spacing: 4) {
                        Image(systemName: "arrow.triangle.2.circlepath")
                            .font(.caption)
                        Text("Switch Role")
                            .font(.caption)
                    }
                    .foregroundColor(.blue)
                }
            }
        }
    }
}

// Quick action buttons for the home view
struct QuickActionButton: View {
    let icon: String
    let title: String
    let subtitle: String

    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.blue)

            Text(title)
                .font(.subheadline)
                .fontWeight(.medium)

            Text(subtitle)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(Color.blue.opacity(0.1))
        .cornerRadius(12)
    }
}

// Role Selection Sheet
struct HomeView: View {
    @AppStorage("userMode") private var userMode: UserMode = .patient
    @State private var selectedRole: UserMode = .patient
    let onRoleSelected: () -> Void

    init(onRoleSelected: @escaping () -> Void = {}) {
        self.onRoleSelected = onRoleSelected
    }

    var body: some View {
        NavigationView {
            ZStack {
                // Background gradient
                LinearGradient(
                    gradient: Gradient(colors: [Color.blue.opacity(0.1), Color.purple.opacity(0.1)]),
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()

                VStack(spacing: 40) {
                    Spacer()

                    // App Logo and Title
                    VStack(spacing: 16) {
                        Image(systemName: "heart.circle.fill")
                            .font(.system(size: 80))
                            .foregroundColor(.blue)

                        Text("ZivoHealth")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                            .foregroundColor(.primary)

                        Text("Smart Healthcare Platform")
                            .font(.title3)
                            .foregroundColor(.secondary)
                    }

                    // Current Role Display
                    VStack(spacing: 12) {
                        Text("Current Role")
                            .font(.headline)
                            .foregroundColor(.secondary)

                        HStack {
                            Image(systemName: userMode == .patient ? "person.circle.fill" : "stethoscope.circle.fill")
                                .font(.title)
                                .foregroundColor(.blue)

                            Text(userMode == .patient ? "Patient" : "Doctor")
                                .font(.title2)
                                .fontWeight(.semibold)
                        }
                        .padding()
                        .background(Color.blue.opacity(0.1))
                        .cornerRadius(12)
                    }

                    Spacer()

                    // Role Selection Cards
                    VStack(spacing: 20) {
                        Text("Switch Role")
                            .font(.title2)
                            .fontWeight(.semibold)
                            .padding(.bottom, 10)

                        // Patient Role Card
                        RoleCard(
                            role: .patient,
                            title: "Patient",
                            subtitle: "Access healthcare services",
                            icon: "person.circle.fill",
                            description: "Chat with AI, consult doctors, and manage your health",
                            isSelected: selectedRole == .patient
                        ) {
                            selectedRole = .patient
                        }

                        // Doctor Role Card
                        RoleCard(
                            role: .doctor,
                            title: "Doctor",
                            subtitle: "Manage patient consultations",
                            icon: "stethoscope.circle.fill",
                            description: "Review consultation requests, manage patient cases, and provide care",
                            isSelected: selectedRole == .doctor
                        ) {
                            selectedRole = .doctor
                        }

                        // Switch Role Button
                        if selectedRole != userMode {
                            Button(action: {
                                userMode = selectedRole

                                // Clear auth token when role changes
                                NetworkService.shared.handleRoleChange()

                                // Notify parent that role was selected
                                onRoleSelected()
                            }) {
                                HStack {
                                    Text("Switch to \(selectedRole == .patient ? "Patient" : "Doctor")")
                                    Image(systemName: "arrow.right")
                                }
                                .font(.headline)
                                .foregroundColor(.white)
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.blue)
                                .cornerRadius(12)
                            }
                            .padding(.horizontal, 40)
                            .padding(.top, 20)
                        }
                    }

                    Spacer()
                }
                .padding()
            }
            .navigationTitle("Switch Role")
            .navigationBarTitleDisplayMode(.inline)
        }
        .onAppear {
            selectedRole = userMode
        }
    }
}

#Preview {
    ContentView()
}

// Patient-specific chat history view wrapper
struct PatientChatHistoryView: View {
    var body: some View {
        ChatHistoryView(fromTab: true)
    }
}
