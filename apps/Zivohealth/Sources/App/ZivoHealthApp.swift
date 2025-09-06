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
                    
                    // Environment-aware endpoint validation
                    validateAndUpdateEndpoint()
                }
                .onChange(of: scenePhase) { newPhase in
                    handleScenePhaseChange(newPhase)
                }
        }
    }
    
    private func validateAndUpdateEndpoint() {
        let currentEndpoint = apiEndpoint
        
        // In local environment, ensure localhost/lan IPs use HTTP (not HTTPS)
        if AppConfig.Environment.current == .local {
            if currentEndpoint.hasPrefix("https://") && (currentEndpoint.contains("localhost") || currentEndpoint.contains("127.0.0.1") || currentEndpoint.contains("192.168")) {
                let httpEndpoint = currentEndpoint.replacingOccurrences(of: "https://", with: "http://")
                apiEndpoint = httpEndpoint
                NetworkService.shared.handleEndpointChange()
                print("🛠 [App] Downgraded endpoint to HTTP for local: \(httpEndpoint)")
            }
            return
        }
        
        // Production/staging rules
        // Force HTTPS for production environments
        if AppConfig.forceHTTPS && currentEndpoint.hasPrefix("http://") {
            let httpsEndpoint = currentEndpoint.replacingOccurrences(of: "http://", with: "https://")
            apiEndpoint = httpsEndpoint
            NetworkService.shared.handleEndpointChange()
            print("🔒 [App] Upgraded endpoint to HTTPS for production: \(httpsEndpoint)")
        }
        
        // Require domain names for production (no local IPs)
        if !AppConfig.allowLocalIP && (currentEndpoint.contains("localhost") || currentEndpoint.contains("192.168") || currentEndpoint.contains("127.0.0.1")) {
            apiEndpoint = AppConfig.defaultAPIEndpoint
            NetworkService.shared.handleEndpointChange()
            print("🌐 [App] Updated endpoint to production domain: \(AppConfig.defaultAPIEndpoint)")
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
