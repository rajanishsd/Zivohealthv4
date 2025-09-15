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
                    
                    // Always ensure we're using the current AppConfig value
                    if apiEndpoint != AppConfig.defaultAPIEndpoint {
                        print("🔄 [App] apiEndpoint '\(apiEndpoint)' differs from AppConfig '\(AppConfig.defaultAPIEndpoint)', updating...")
                        
                        // Check if we should clear tokens based on pre-deploy configuration
                        let shouldClearTokens = AppConfig.shouldClearTokensOnEnvironmentSwitch
                        let isSwitchingEnvironments = isDifferentEnvironmentType(from: apiEndpoint, to: AppConfig.defaultAPIEndpoint)
                        
                        if shouldClearTokens && isSwitchingEnvironments {
                            print("⚠️ [App] Environment switch detected + shouldClearTokensOnEnvironmentSwitch=true - clearing tokens")
                            apiEndpoint = AppConfig.defaultAPIEndpoint
                            NetworkService.shared.handleEndpointChange()
                        } else {
                            print("ℹ️ [App] Updating endpoint - tokens preserved (shouldClearTokensOnEnvironmentSwitch=\(shouldClearTokens))")
                            apiEndpoint = AppConfig.defaultAPIEndpoint
                            NetworkService.shared.resetToAppConfigEndpoint()
                        }
                    } else {
                        print("✅ [App] apiEndpoint matches AppConfig: \(apiEndpoint)")
                    }
                    
                    // Debug: Check authentication state
                    print("🔍 [App] Authentication state check:")
                    print("   - hasStoredTokens: \(NetworkService.shared.hasStoredTokens())")
                    print("   - isAuthenticated: \(NetworkService.shared.isAuthenticated())")
                    
                    // Debug: Print detailed network service state
                    NetworkService.shared.debugAuthenticationState()
                    
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
    
    // MARK: - Helper Functions
    
    /// Determines if we're switching between different environment types
    /// This helps decide whether to clear stored tokens for security
    private func isDifferentEnvironmentType(from oldEndpoint: String, to newEndpoint: String) -> Bool {
        // Define environment types
        let isProduction = oldEndpoint.contains("api.zivohealth.ai")
        let isStaging = oldEndpoint.contains("staging-api.zivohealth.ai")
        let isLocal = oldEndpoint.contains("192.168") || oldEndpoint.contains("localhost") || oldEndpoint.contains("127.0.0.1")
        
        let isNewProduction = newEndpoint.contains("api.zivohealth.ai")
        let isNewStaging = newEndpoint.contains("staging-api.zivohealth.ai")
        let isNewLocal = newEndpoint.contains("192.168") || newEndpoint.contains("localhost") || newEndpoint.contains("127.0.0.1")
        
        // Check if we're switching between different environment types
        let switchingFromProduction = isProduction && (isNewStaging || isNewLocal)
        let switchingFromStaging = isStaging && (isNewProduction || isNewLocal)
        let switchingFromLocal = isLocal && (isNewProduction || isNewStaging)
        
        return switchingFromProduction || switchingFromStaging || switchingFromLocal
    }
}
