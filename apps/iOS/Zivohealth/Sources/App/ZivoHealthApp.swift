import SwiftUI
import FirebaseCore
import FirebaseMessaging
import UserNotifications

@main
struct ZivoHealthApp: App {
    @Environment(\.scenePhase) var scenePhase
    @AppStorage("apiEndpoint") private var apiEndpoint = AppConfig.defaultAPIEndpoint
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
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
                    // Debug: Verify stored user id for reminders
                    let kcUid = KeychainService.shared.retrieve(key: "zivo_user_id")
                    let udUid = UserDefaults.standard.string(forKey: "zivo_user_id")
                    print("🔎 [Reminders] zivo_user_id (Keychain)=\(kcUid ?? "nil"), (UserDefaults)=\(udUid ?? "nil")")
                    
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

                    // Attempt immediate FCM token fetch and register if available
                    Messaging.messaging().token { token, error in
                        if let error = error {
                            print("⚠️ [Reminders] Failed to fetch FCM token immediately: \(error)")
                            return
                        }
                        guard let token = token else {
                            print("ℹ️ [Reminders] FCM token not yet available; will wait for delegate callback")
                            return
                        }
                        let userId = KeychainService.shared.retrieve(key: "zivo_user_id") ?? UserDefaults.standard.string(forKey: "zivo_user_id") ?? ""
                        let apiKey = AppConfig.apiKey
                        print("📬 [Reminders] Immediate FCM token fetched: \(token.prefix(12))...")
                        print("👤 [Reminders] Immediate register with user_id=\(userId.isEmpty ? "<empty>" : userId)")
                        guard !userId.isEmpty, !apiKey.isEmpty else { return }
                        ReminderAPIService.shared.registerDevice(userId: userId, fcmToken: token, apiKey: apiKey, completion: nil)
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

class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate, MessagingDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey : Any]? = nil) -> Bool {
        FirebaseApp.configure()
        UNUserNotificationCenter.current().delegate = self
        
        // Check if push notifications are available
        print("🔍 [Notifications] Checking push notification availability...")
        if application.isRegisteredForRemoteNotifications {
            print("✅ [Notifications] App is already registered for remote notifications")
        } else {
            print("ℹ️ [Notifications] App is not yet registered for remote notifications")
        }
        // Check current notification settings first
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            print("🔍 [Notifications] Current settings: authorizationStatus=\(settings.authorizationStatus.rawValue), alertSetting=\(settings.alertSetting.rawValue)")
        }
        
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, error in
            print("🔔 [Notifications] Permission request result: granted=\(granted), error=\(error?.localizedDescription ?? "none")")
            if granted {
                print("✅ [Notifications] Permission granted - registering for remote notifications")
                DispatchQueue.main.async { 
                    print("📱 [Notifications] About to call registerForRemoteNotifications()")
                    UIApplication.shared.registerForRemoteNotifications()
                    print("📱 [Notifications] registerForRemoteNotifications() called")
                    
                    // Force a delay and retry if needed
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                        if !UIApplication.shared.isRegisteredForRemoteNotifications {
                            print("🔄 [Notifications] Retrying APNs registration...")
                            UIApplication.shared.registerForRemoteNotifications()
                        }
                    }
                }
            } else {
                print("❌ [Notifications] Permission denied - cannot register for remote notifications")
            }
        }
        Messaging.messaging().delegate = self
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        print("🎉 [APNs] SUCCESS! APNs registration completed!")
        print("📱 [APNs] Device token received - length: \(deviceToken.count) bytes")
        
        Messaging.messaging().apnsToken = deviceToken
        
        // Convert APNs device token to hexadecimal string for logging
        let apnsTokenString = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        print("📱 [Reminders] APNs device token set (length=\(deviceToken.count))")
        print("🔑 [Reminders] APNs Device Token: \(apnsTokenString)")
        print("🔑 [Reminders] APNs Token (for Apple Developer site): \(apnsTokenString)")
        // After APNs token is set, retrieve FCM token to ensure registration happens
        Messaging.messaging().token { token, error in
            if let error = error {
                print("⚠️ [Reminders] Failed to fetch FCM token after APNs set: \(error)")
                return
            }
            guard let token = token else {
                print("ℹ️ [Reminders] FCM token still unavailable after APNs set")
                return
            }
            let userId = KeychainService.shared.retrieve(key: "zivo_user_id") ?? UserDefaults.standard.string(forKey: "zivo_user_id") ?? ""
            let apiKey = AppConfig.apiKey
            print("📬 [Reminders] FCM token after APNs set: \(token.prefix(12))...")
            print("🔑 [Reminders] FCM Token (for backend): \(token)")
            print("👤 [Reminders] Register after APNs set with user_id=\(userId.isEmpty ? "<empty>" : userId)")
            guard !userId.isEmpty, !apiKey.isEmpty else { return }
            ReminderAPIService.shared.registerDevice(userId: userId, fcmToken: token, apiKey: apiKey, completion: nil)
        }
    }

    nonisolated func messaging(_ messaging: Messaging, didReceiveRegistrationToken fcmToken: String?) {
        guard let token = fcmToken else { return }
        // Debug: Log FCM token received
        print("📬 [Reminders] FCM token received: \(token)")
        
        // Store the FCM token temporarily for later registration
        UserDefaults.standard.set(token, forKey: "pending_fcm_token")
        print("💾 [Reminders] Stored FCM token for later registration")
        
        let userId = KeychainService.shared.retrieve(key: "zivo_user_id") ?? UserDefaults.standard.string(forKey: "zivo_user_id") ?? ""
        print("👤 [Reminders] Using user_id (Keychain→Defaults)=\(userId.isEmpty ? "<empty>" : userId)")
        
        let apiKey = AppConfig.apiKey
        if !userId.isEmpty && !apiKey.isEmpty {
            print("🌐 [Reminders] User already logged in - registering device token immediately")
            ReminderAPIService.shared.registerDevice(userId: userId, fcmToken: token, apiKey: apiKey, completion: nil)
        } else {
            print("⏳ [Reminders] User not logged in - FCM token stored for registration after login")
        }
    }
    
    // Call this after successful login to register any pending FCM token
    static func registerPendingFCMTokenIfNeeded() {
        guard let pendingToken = UserDefaults.standard.string(forKey: "pending_fcm_token"),
              !pendingToken.isEmpty else {
            print("📭 [Reminders] No pending FCM token to register")
            return
        }
        
        let userId = KeychainService.shared.retrieve(key: "zivo_user_id") ?? UserDefaults.standard.string(forKey: "zivo_user_id") ?? ""
        let apiKey = AppConfig.apiKey
        
        guard !userId.isEmpty, !apiKey.isEmpty else {
            print("⚠️ [Reminders] Cannot register pending FCM token - missing user_id or apiKey")
            return
        }
        
        print("🌐 [Reminders] Registering pending FCM token after login")
        ReminderAPIService.shared.registerDevice(userId: userId, fcmToken: pendingToken, apiKey: apiKey) { error in
            if error == nil {
                print("✅ [Reminders] Successfully registered pending FCM token")
                // Clear the pending token since it's now registered
                UserDefaults.standard.removeObject(forKey: "pending_fcm_token")
            } else {
                print("❌ [Reminders] Failed to register pending FCM token: \(error?.localizedDescription ?? "Unknown error")")
            }
        }
    }
    
    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        print("❌ [Notifications] Failed to register for remote notifications: \(error.localizedDescription)")
        print("🔍 [Notifications] Error details: \(error)")
        print("🔍 [Notifications] Error domain: \(error._domain)")
        print("🔍 [Notifications] Error code: \(error._code)")
    }
}
