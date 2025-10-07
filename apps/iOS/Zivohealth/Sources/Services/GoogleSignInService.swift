import Foundation
import GoogleSignIn
import SwiftUI

@MainActor
final class GoogleSignInService: ObservableObject {
    static let shared = GoogleSignInService()
    
    @Published var isSignedIn = false
    @Published var currentUser: GIDGoogleUser?
    @Published var error: String?
    
    private init() {
        setupGoogleSignIn()
    }
    
    // MARK: - Setup
    private func setupGoogleSignIn() {
        // Configure Google Sign-In
        var resolvedClientId: String?
        if let path = Bundle.main.path(forResource: "GoogleService-Info", ofType: "plist"),
           let plist = NSDictionary(contentsOfFile: path),
           let clientId = plist["CLIENT_ID"] as? String,
           !clientId.contains("YOUR_GOOGLE_CLIENT_ID_HERE") {
            resolvedClientId = clientId
        } else if let infoPlistClientId = Bundle.main.object(forInfoDictionaryKey: "GIDClientID") as? String,
                  !infoPlistClientId.isEmpty {
            resolvedClientId = infoPlistClientId
        }
        
        guard let clientId = resolvedClientId else {
            print("❌ [GoogleSignIn] Google client ID not found in GoogleService-Info.plist or Info.plist (GIDClientID)")
            return
        }
        
        GIDSignIn.sharedInstance.configuration = GIDConfiguration(clientID: clientId)
        print("✅ [GoogleSignIn] Configured with client ID: \(clientId)")
    }
    
    // MARK: - Sign In
    func signIn() async throws -> GIDGoogleUser {
        print("🔐 [GoogleSignIn] Starting Google Sign-In flow")
        
        // Check if Google Sign-In is properly configured
        guard GIDSignIn.sharedInstance.configuration != nil else {
            throw GoogleSignInError.configurationError
        }
        
        guard let presentingViewController = await UIApplication.shared.windows.first?.rootViewController else {
            throw GoogleSignInError.noPresentingViewController
        }
        
        do {
            let result = try await GIDSignIn.sharedInstance.signIn(withPresenting: presentingViewController)
            let user = result.user
            
            // Update state
            currentUser = user
            isSignedIn = true
            error = nil
            
            print("✅ [GoogleSignIn] Sign-in successful for user: \(user.profile?.email ?? "unknown")")
            return user
            
        } catch {
            print("❌ [GoogleSignIn] Sign-in failed: \(error)")
            self.error = error.localizedDescription
            throw error
        }
    }
    
    // MARK: - Sign Out
    func signOut() {
        print("🔐 [GoogleSignIn] Signing out")
        GIDSignIn.sharedInstance.signOut()
        currentUser = nil
        isSignedIn = false
        error = nil
    }
    
    // MARK: - Get ID Token
    func getIdToken() async throws -> String {
        guard let user = currentUser else {
            throw GoogleSignInError.notSignedIn
        }
        
        do {
            let idToken = try await user.idToken?.tokenString
            guard let token = idToken else {
                throw GoogleSignInError.noIdToken
            }
            
            print("✅ [GoogleSignIn] Retrieved ID token")
            return token
            
        } catch {
            print("❌ [GoogleSignIn] Failed to get ID token: \(error)")
            throw error
        }
    }
    
    // MARK: - Restore Previous Sign-In
    func restorePreviousSignIn() async {
        print("🔐 [GoogleSignIn] Restoring previous sign-in")
        
        do {
            let user = try await GIDSignIn.sharedInstance.restorePreviousSignIn()
            currentUser = user
            isSignedIn = true
            error = nil
            print("✅ [GoogleSignIn] Previous sign-in restored for: \(user.profile?.email ?? "unknown")")
        } catch {
            print("ℹ️ [GoogleSignIn] No previous sign-in to restore: \(error)")
            currentUser = nil
            isSignedIn = false
        }
    }
    
    // MARK: - Handle URL
    func handleURL(_ url: URL) -> Bool {
        return GIDSignIn.sharedInstance.handle(url)
    }
}

// MARK: - Error Types
enum GoogleSignInError: LocalizedError {
    case noPresentingViewController
    case notSignedIn
    case noIdToken
    case configurationError
    
    var errorDescription: String? {
        switch self {
        case .noPresentingViewController:
            return "No presenting view controller available"
        case .notSignedIn:
            return "User is not signed in"
        case .noIdToken:
            return "No ID token available"
        case .configurationError:
            return "Google Sign-In configuration error"
        }
    }
}

// MARK: - App Delegate Integration
extension GoogleSignInService {
    func configureForAppDelegate() {
        // This should be called in AppDelegate or App struct
        setupGoogleSignIn()
    }
}
