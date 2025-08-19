import SwiftUI
import UIKit

@main
struct ZivoHealthApp: App {
    @Environment(\.scenePhase) var scenePhase
    @AppStorage("apiEndpoint") private var apiEndpoint = ""
    
    init() {
        // Global appearances
        let tabBarAppearance = UITabBarAppearance()
        tabBarAppearance.configureWithOpaqueBackground()
        tabBarAppearance.backgroundColor = UIColor.systemBackground
        tabBarAppearance.stackedLayoutAppearance.selected.iconColor = BrandTheme.brandRedUIColor
        tabBarAppearance.stackedLayoutAppearance.selected.titleTextAttributes = [.foregroundColor: BrandTheme.brandRedUIColor]

        UITabBar.appearance().tintColor = BrandTheme.brandRedUIColor
        UITabBar.appearance().standardAppearance = tabBarAppearance
        UITabBar.appearance().scrollEdgeAppearance = tabBarAppearance

        let navAppearance = UINavigationBarAppearance()
        navAppearance.configureWithOpaqueBackground()
        navAppearance.backgroundColor = UIColor.systemBackground
        navAppearance.titleTextAttributes = [.foregroundColor: BrandTheme.brandRedUIColor]
        navAppearance.largeTitleTextAttributes = [.foregroundColor: BrandTheme.brandRedUIColor]
        UINavigationBar.appearance().tintColor = BrandTheme.brandRedUIColor
        UINavigationBar.appearance().standardAppearance = navAppearance
        UINavigationBar.appearance().scrollEdgeAppearance = navAppearance
    }
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .onChange(of: scenePhase) { newPhase in
                    handleScenePhaseChange(newPhase)
                }
                .onAppear {
                    // Seed default endpoint on first launch if empty
                    if apiEndpoint.isEmpty {
                        apiEndpoint = AppConfig.defaultAPIEndpoint
                    }
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
