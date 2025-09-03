import SwiftUI

@main
struct ZivoHealthApp: App {
    @Environment(\.scenePhase) var scenePhase
    @AppStorage("apiEndpoint") private var apiEndpoint = ""
    
    init() {
        // Configure tab bar appearance globally to prevent transparency
        let tabBarAppearance = UITabBarAppearance()
        tabBarAppearance.configureWithOpaqueBackground()
        tabBarAppearance.backgroundColor = UIColor.systemBackground
        
        UITabBar.appearance().standardAppearance = tabBarAppearance
        UITabBar.appearance().scrollEdgeAppearance = tabBarAppearance
    }
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .tint(.zivoRed)
                .onAppear {
                    // Seed default endpoint on first launch if empty
                    if apiEndpoint.isEmpty {
                        apiEndpoint = AppConfig.defaultAPIEndpoint
                    }
                    // One-time migration: force HTTPS domain if an old http/IP endpoint is detected
                    if apiEndpoint.hasPrefix("http://3.208.12.170") || (apiEndpoint.hasPrefix("http://") && !apiEndpoint.contains("zivohealth.ai")) {
                        apiEndpoint = "https://api.zivohealth.ai"
                        NetworkService.shared.handleEndpointChange()
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
