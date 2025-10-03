import Foundation
import Security

class KeychainService {
    static let shared = KeychainService()
    private init() {}

    // MARK: - Basic Ops
    func store(key: String, value: String) -> Bool {
        guard let data = value.data(using: .utf8) else { return false }
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecValueData as String: data
        ]
        SecItemDelete(query as CFDictionary)
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
              let value = String(data: data, encoding: .utf8) else { return nil }
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
        let query: [String: Any] = [ kSecClass as String: kSecClassGenericPassword ]
        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess
    }

    // MARK: - Doctor-only helpers
    private let authKey = "doctor_auth_token"
    private let refreshKey = "doctor_refresh_token"

    func storeDoctorToken(_ token: String) -> Bool { store(key: authKey, value: token) }
    func retrieveDoctorToken() -> String? { retrieve(key: authKey) }
    func deleteDoctorToken() -> Bool { delete(key: authKey) }

    func storeDoctorRefresh(_ token: String) -> Bool { store(key: refreshKey, value: token) }
    func retrieveDoctorRefresh() -> String? { retrieve(key: refreshKey) }
    func deleteDoctorRefresh() -> Bool { delete(key: refreshKey) }

    func clearDoctorTokens() -> Bool { deleteDoctorToken() && deleteDoctorRefresh() }
}


