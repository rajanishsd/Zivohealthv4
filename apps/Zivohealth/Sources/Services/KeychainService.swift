import Foundation
import Security

class KeychainService {
    static let shared = KeychainService()
    
    private init() {}
    
    // MARK: - Keychain Operations
    
    func store(key: String, value: String) -> Bool {
        let data = value.data(using: .utf8)!
        
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecValueData as String: data
        ]
        
        // Delete any existing item
        SecItemDelete(query as CFDictionary)
        
        // Add new item
        let status = SecItemAdd(query as CFDictionary, nil)
        return status == errSecSuccess
    }
    
    func retrieve(key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        
        guard status == errSecSuccess,
              let data = result as? Data,
              let value = String(data: data, encoding: .utf8) else {
            return nil
        }
        
        return value
    }
    
    func delete(key: String) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key
        ]
        
        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess
    }
    
    func clearAll() -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword
        ]
        
        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess
    }
    
    // MARK: - Token Management
    
    func storeToken(_ token: String, for userMode: UserMode) -> Bool {
        let key = "\(userMode.rawValue)_auth_token"
        print("🔐 [KeychainService] Storing token for \(userMode) - Key: \(key), Token length: \(token.count)")
        let result = store(key: key, value: token)
        print("🔐 [KeychainService] Store result: \(result)")
        return result
    }
    
    func retrieveToken(for userMode: UserMode) -> String? {
        let key = "\(userMode.rawValue)_auth_token"
        let token = retrieve(key: key)
        print("🔐 [KeychainService] Retrieved token for \(userMode) - Key: \(key): \(token != nil ? "Found (\(token?.count ?? 0) chars)" : "Not found")")
        return token
    }
    
    func storeRefreshToken(_ token: String, for userMode: UserMode) -> Bool {
        let key = "\(userMode.rawValue)_refresh_token"
        print("🔐 [KeychainService] Storing refresh token for \(userMode)")
        return store(key: key, value: token)
    }
    
    func retrieveRefreshToken(for userMode: UserMode) -> String? {
        let key = "\(userMode.rawValue)_refresh_token"
        let token = retrieve(key: key)
        print("🔐 [KeychainService] Retrieved refresh token for \(userMode): \(token != nil ? "Found" : "Not found")")
        return token
    }
    
    func clearTokens(for userMode: UserMode) -> Bool {
        let authKey = "\(userMode.rawValue)_auth_token"
        let refreshKey = "\(userMode.rawValue)_refresh_token"
        
        let authDeleted = delete(key: authKey)
        let refreshDeleted = delete(key: refreshKey)
        
        print("🔐 [KeychainService] Cleared tokens for \(userMode): auth=\(authDeleted), refresh=\(refreshDeleted)")
        return authDeleted && refreshDeleted
    }
    
    func clearAllTokens() -> Bool {
        print("🔐 [KeychainService] Clearing all tokens from Keychain")
        return clearAll()
    }
    
    func hasStoredTokens(for userMode: UserMode) -> Bool {
        let authToken = retrieveToken(for: userMode)
        let refreshToken = retrieveRefreshToken(for: userMode)
        let hasTokens = authToken != nil || refreshToken != nil
        print("🔐 [KeychainService] Has stored tokens for \(userMode): \(hasTokens)")
        return hasTokens
    }
}
