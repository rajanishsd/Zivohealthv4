import SwiftUI
import UIKit

struct ContentView: View {
    @AppStorage("userMode") private var userMode: UserMode = .patient
    @State private var selectedTab = 0
    @State private var isInitializing = true
    @ObservedObject private var networkService = NetworkService.shared
    @State private var showReportSheet = false
    @State private var pendingScreenshot: UIImage? = nil

    var body: some View {
        if isInitializing {
            // Show loading screen while checking authentication
            VStack {
                ProgressView()
                Text("Initializing...")
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color.white)
            .onAppear {
                Task {
                    await initializeAuth()
                }
            }
        } else if !networkService.isAuthenticatedState {
            if #available(iOS 16.0, *) {
                NavigationStack { 
                    DualLoginView { 
                        // Login successful - authentication state will be updated automatically by NetworkService
                    } 
                }
            } else {
                NavigationView { 
                    DualLoginView { 
                        // Login successful - authentication state will be updated automatically by NetworkService
                    } 
                }
            }
        } else if !networkService.isOnboardingCompleted() {
            // Show onboarding flow for authenticated users who haven't completed onboarding
            OnboardingFlowView(
                prefilledEmail: networkService.currentUserEmail,
                prefilledFullName: networkService.currentUserFullName
            )
            .environmentObject(networkService)
                .onAppear {
                    print("📋 [ContentView] Showing onboarding flow - user is authenticated but onboarding not completed")
                }
        } else {
            // Show main app with role-based navigation
            if #available(iOS 16.0, *) {
                NavigationStack {
                    TabView(selection: $selectedTab) {
                        // Home Tab
                        HomeView()
                        .tabItem {
                            Label("Home", systemImage: "house.fill")
                        }
                        .tag(0)

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

                        ProfileView()
                        .tabItem {
                            Label("Profile", systemImage: "person.crop.circle")
                        }
                        .tag(4)
                    }
                    .onReceive(NotificationCenter.default.publisher(for: Notification.Name("SwitchToChatTab"))) { _ in
                        selectedTab = 2 // Chat tab for patients
                    }
                    .onReceive(NotificationCenter.default.publisher(for: Notification.Name("SwitchToAppointmentsTab"))) { _ in
                        selectedTab = 3 // Appointments tab
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
                        print("🏠 [ContentView] Showing main app - user is authenticated and onboarding completed")
                        // Configure tab bar appearance to be solid and prevent transparency
                        let tabBarAppearance = UITabBarAppearance()
                        tabBarAppearance.configureWithOpaqueBackground()
                        tabBarAppearance.backgroundColor = UIColor.systemBackground
                        
                        UITabBar.appearance().standardAppearance = tabBarAppearance
                        UITabBar.appearance().scrollEdgeAppearance = tabBarAppearance
                    }
                    .onReceive(NotificationCenter.default.publisher(for: UIApplication.userDidTakeScreenshotNotification)) { _ in
                        // Capture a screenshot of current UI and prompt to report
                        if let img = ScreenCapture.captureCurrentWindow() {
                            self.pendingScreenshot = img
                            self.showReportSheet = true
                        }
                    }
                }
                .overlay(alignment: .topTrailing) {
                    Button(action: { triggerReport() }) {
                        Image(systemName: "ladybug.fill")
                            .font(.system(size: 14, weight: .bold))
                            .foregroundColor(.white)
                            .padding(8)
                            .background(Color.red)
                            .clipShape(Circle())
                            .shadow(radius: 2)
                    }
                    .padding(.trailing, 8)
                    .padding(.top, 48)
                    .accessibilityLabel("Report an issue")
                }
                .sheet(isPresented: $showReportSheet) {
                    if let img = pendingScreenshot {
                        ReportIssueSheet(image: img) { category, description in
                            try await FeedbackReporter.shared.report(image: img, category: category, description: description, route: nil)
                        }
                    }
                }
            } else {
                // iOS 15 fallback - keep original NavigationView
            NavigationView {
                TabView(selection: $selectedTab) {
                    // Home Tab
                    HomeView()
                    .tabItem {
                        Label("Home", systemImage: "house.fill")
                    }
                    .tag(0)

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

                    ProfileView()
                    .tabItem {
                        Label("Profile", systemImage: "person.crop.circle")
                    }
                    .tag(4)
                }
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
                .overlay(alignment: .topTrailing) {
                    Button(action: { triggerReport() }) {
                        Image(systemName: "ladybug.fill")
                            .font(.system(size: 14, weight: .bold))
                            .foregroundColor(.white)
                            .padding(8)
                            .background(Color.red)
                            .clipShape(Circle())
                            .shadow(radius: 2)
                    }
                    .padding(.trailing, 8)
                    .padding(.top, 48)
                    .accessibilityLabel("Report an issue")
                }
                .sheet(isPresented: $showReportSheet) {
                    if let img = pendingScreenshot {
                        ReportIssueSheet(image: img) { category, description in
                            try await FeedbackReporter.shared.report(image: img, category: category, description: description, route: nil)
                        }
                    }
                }
            }
            }
        }
        reportSheetPresenter
    }
    
    // MARK: - Authentication Initialization
    
    private func initializeAuth() async {
        print("🚀 [ContentView] Initializing authentication...")
        
        // Small delay to ensure AppStorage values are loaded
        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds
        
        // Force Zivohealth app to Patient mode only
        await MainActor.run {
            if userMode != .patient {
                userMode = .patient
                NetworkService.shared.handleRoleChange()
            }
        }
        
        // Check initial state
        let hasTokens = NetworkService.shared.hasStoredTokens()
        print("🔍 [ContentView] Has stored tokens: \(hasTokens)")
        
        // Initialize NetworkService authentication
        await NetworkService.shared.initializeAuthentication()
        
        // Check if user is authenticated
        let authenticated = NetworkService.shared.isAuthenticated()
        print("🔍 [ContentView] Final authentication state: \(authenticated)")
        
        await MainActor.run {
            isInitializing = false
            print("✅ [ContentView] Authentication check complete: \(authenticated ? "Authenticated" : "Not authenticated")")
        }
    }
}

// Quick action buttons for the home view (kept for backward compatibility)
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

#Preview {
    ContentView()
}

// Patient-specific chat history view wrapper
struct PatientChatHistoryView: View {
    var body: some View {
        ChatHistoryView(fromTab: true)
    }
}

// Present report sheet for feedback submission
extension ContentView {
    @ViewBuilder
    private var reportSheetPresenter: some View {
        EmptyView()
            .sheet(isPresented: $showReportSheet) {
                if let img = pendingScreenshot {
                    ReportIssueSheet(image: img) { category, description in
                        try await FeedbackReporter.shared.report(image: img, category: category, description: description, route: nil)
                    }
                }
            }
    }

    private func triggerReport() {
        if let img = ScreenCapture.captureCurrentWindow() {
            self.pendingScreenshot = img
            self.showReportSheet = true
        }
    }
}
