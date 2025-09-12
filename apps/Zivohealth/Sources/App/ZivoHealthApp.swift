import SwiftUI

@main
struct ZivoHealthApp: App {
    @Environment(\.scenePhase) var scenePhase
    @AppStorage("apiEndpoint") private var apiEndpoint = AppConfig.defaultAPIEndpoint
    
    init() {
        // Configure tab bar appearance globally to prevent transparency
        let tabBarAppearance = UITabBarAppearance()
        tabBarAppearance.configureWithOpaqueBackground()
        tabBarAppearance.backgroundColor = UIColor.systemBackground
        
        UITabBar.appearance().standardAppearance = tabBarAppearance
        UITabBar.appearance().scrollEdgeAppearance = tabBarAppearance
        
        // Configure Google Sign-In
        GoogleSignInService.shared.configureForAppDelegate()
    }
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .tint(.zivoRed)
                .onAppear {
                    print("🚀 [App] onAppear - Current apiEndpoint: '\(apiEndpoint)'")
                    print("🚀 [App] onAppear - AppConfig.defaultAPIEndpoint: '\(AppConfig.defaultAPIEndpoint)'")
                    
                    // Only validate and update endpoint if it's empty or invalid
                    if apiEndpoint.isEmpty {
                        print("🔄 [App] apiEndpoint is empty, setting to default: \(AppConfig.defaultAPIEndpoint)")
                        apiEndpoint = AppConfig.defaultAPIEndpoint
                        // Don't call handleEndpointChange() here since this is just initialization
                    } else {
                        print("✅ [App] apiEndpoint already set: \(apiEndpoint)")
                        // Only validate if the endpoint looks suspicious (contains local IPs in production)
                        if AppConfig.Environment.current == .production && 
                           (apiEndpoint.contains("localhost") || apiEndpoint.contains("192.168") || apiEndpoint.contains("127.0.0.1")) {
                            print("⚠️ [App] Detected local IP in production, updating to production endpoint")
                            apiEndpoint = AppConfig.defaultAPIEndpoint
                            NetworkService.shared.handleEndpointChange()
                        } else {
                            print("✅ [App] Endpoint looks valid, no changes needed")
                        }
                    }
                    
                    // Debug: Check authentication state
                    print("🔍 [App] Authentication state check:")
                    print("   - hasStoredTokens: \(NetworkService.shared.hasStoredTokens())")
                    print("   - isAuthenticated: \(NetworkService.shared.isAuthenticated())")
                    
                    // Restore previous Google Sign-In session
                    Task {
                        await GoogleSignInService.shared.restorePreviousSignIn()
                    }
                }
                .onChange(of: scenePhase) { newPhase in
                    handleScenePhaseChange(newPhase)
                }
        }
    }
    
    
    private func handleScenePhaseChange(_ newPhase: ScenePhase) {
        switch newPhase {
        case .active:
            print("🟢 [App] App became active - resuming network activities")
            // App became active - resume network connections
            NetworkService.shared.handleAppDidBecomeActive()
            
        case .inactive:
            print("🟡 [App] App became inactive")
            // App became inactive - prepare for background
            
        case .background:
            print("🔴 [App] App entered background - pausing network activities")
            // App entered background - pause non-critical network activities
            NetworkService.shared.handleAppDidEnterBackground()
            
        @unknown default:
            break
        }
    }
}
