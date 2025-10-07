import Foundation
import HealthKit
import SwiftUI


final class HealthKitAuthorizationService: ObservableObject, @unchecked Sendable {
    static let shared = HealthKitAuthorizationService()
    
    private let healthStore = HKHealthStore()
    
    // Published properties for UI updates
    @Published var isAuthorized = false
    @Published var errorMessage: String?
    @Published var showingAlert = false
    @Published var alertMessage = ""
    
    private init() {}
    
    // MARK: - Public Interface
    
    // Public provider for all read types used by the app (for HealthKitUI requests)
    static func allReadTypes() -> Set<HKObjectType> {
        var types: [HKObjectType] = []
        // Basic health metrics
        if let heartRate = HKObjectType.quantityType(forIdentifier: .heartRate) { types.append(heartRate) }
        if let stepCount = HKObjectType.quantityType(forIdentifier: .stepCount) { types.append(stepCount) }
        if let activeEnergy = HKObjectType.quantityType(forIdentifier: .activeEnergyBurned) { types.append(activeEnergy) }
        if let bodyMass = HKObjectType.quantityType(forIdentifier: .bodyMass) { types.append(bodyMass) }
        if let bodyTemp = HKObjectType.quantityType(forIdentifier: .bodyTemperature) { types.append(bodyTemp) }
        // Blood pressure
        if let systolic = HKObjectType.quantityType(forIdentifier: .bloodPressureSystolic) { types.append(systolic) }
        if let diastolic = HKObjectType.quantityType(forIdentifier: .bloodPressureDiastolic) { types.append(diastolic) }
        // Blood glucose
        if let glucose = HKObjectType.quantityType(forIdentifier: .bloodGlucose) { types.append(glucose) }
        // Activity metrics
        if let standTime = HKObjectType.quantityType(forIdentifier: .appleStandTime) { types.append(standTime) }
        if let flights = HKObjectType.quantityType(forIdentifier: .flightsClimbed) { types.append(flights) }
        // Workouts and sleep
        types.append(HKObjectType.workoutType())
        if let sleep = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) { types.append(sleep) }
        return Set(types)
    }
    
    // Optional types that we request if available but do not gate connection on
    private func optionalReadTypes() -> [HKObjectType] {
        var types: [HKObjectType] = []
        if let systolic = HKObjectType.quantityType(forIdentifier: .bloodPressureSystolic) { types.append(systolic) }
        if let diastolic = HKObjectType.quantityType(forIdentifier: .bloodPressureDiastolic) { types.append(diastolic) }
        if let glucose = HKObjectType.quantityType(forIdentifier: .bloodGlucose) { types.append(glucose) }
        if let temperature = HKObjectType.quantityType(forIdentifier: .bodyTemperature) { types.append(temperature) }
        if let bodyMass = HKObjectType.quantityType(forIdentifier: .bodyMass) { types.append(bodyMass) }
        if let standTime = HKObjectType.quantityType(forIdentifier: .appleStandTime) { types.append(standTime) }
        if let flights = HKObjectType.quantityType(forIdentifier: .flightsClimbed) { types.append(flights) }
        if let sleep = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) { types.append(sleep) }
        return types
    }
    
    private func name(for type: HKObjectType) -> String {
        switch type {
        case is HKQuantityType:
            let qt = type as! HKQuantityType
            return qt.identifier
        case is HKCategoryType:
            let ct = type as! HKCategoryType
            return ct.identifier
        case is HKWorkoutType:
            return "workoutType"
        default:
            return "unknown"
        }
    }
    
    /// Check if HealthKit is available and properly configured
    func isHealthKitAvailable() -> Bool {
        return HKHealthStore.isHealthDataAvailable()
    }
    
    /// Get current authorization status for health data
    func getCurrentAuthorizationStatus() -> HKAuthorizationStatus {
        guard isHealthKitAvailable() else { return .notDetermined }
        
        let essentialTypes = Array(Self.allReadTypes())
        var anyAuthorized = false
        var anyDenied = false
        
        for type in essentialTypes {
            let status = healthStore.authorizationStatus(for: type)
            print("🔎 Essential type \(name(for: type)) status: \(status.rawValue)")
            if status == .sharingAuthorized { anyAuthorized = true }
            if status == .sharingDenied { anyDenied = true }
        }
        
        if anyAuthorized { return .sharingAuthorized }
        if anyDenied { return .sharingDenied }
        return .notDetermined
    }
    
    /// Request HealthKit authorization with comprehensive error handling
    func requestAuthorization() async -> Bool {
        guard isHealthKitAvailable() else {
            isAuthorized = false
            errorMessage = "Health data is not available on this device"
            return false
        }
        
        let currentStatus = getCurrentAuthorizationStatus()
        print("🔍 Requesting authorization, current status: \(currentStatus.rawValue)")
        
        // Do not early-return on denied; allow re-request to refresh OS state after Settings changes
        
        // If already authorized, return true
        if currentStatus == .sharingAuthorized {
            print("✅ HealthKit already authorized")
            isAuthorized = true
            errorMessage = nil
            return true
        }
        
        // Request authorization for all declared read types
        let typesToRead: Set<HKObjectType> = Self.allReadTypes()
        
        return await withCheckedContinuation { continuation in
            healthStore.requestAuthorization(toShare: nil, read: typesToRead) { [weak self] success, error in
                Task {
                    if success {
                        // Verify essential authorization was actually granted
                        guard let self else { continuation.resume(returning: false); return }
                        let essentialTypes = Array(Self.allReadTypes())
                        var anyAuthorized = false
                        var deniedTypes: [String] = []
                        
                        for type in essentialTypes {
                            let status = self.healthStore.authorizationStatus(for: type)
                            print("✅ Post-request essential type \(self.name(for: type)) status: \(status.rawValue)")
                            if status == .sharingAuthorized { anyAuthorized = true }
                            if status == .sharingDenied { deniedTypes.append(self.name(for: type)) }
                        }
                        if anyAuthorized {
                            self.isAuthorized = true
                            self.errorMessage = nil
                            continuation.resume(returning: true)
                        } else {
                            self.isAuthorized = false
                            if !deniedTypes.isEmpty {
                                self.errorMessage = "HealthKit access denied for: \(deniedTypes.joined(separator: ", ")). Enable in Settings > Privacy & Security > Health > Data Access & Devices > Zivohealth"
                            } else {
                                self.errorMessage = "HealthKit authorization was not granted. Please try again."
                            }
                            continuation.resume(returning: false)
                        }
                    } else {
                        self?.isAuthorized = false
                        self?.errorMessage = error?.localizedDescription ?? "Failed to request HealthKit authorization"
                        continuation.resume(returning: false)
                    }
                }
            }
        }
    }
    
    /// Check and update authorization status without requesting
    func checkAuthorizationStatus() {
        guard isHealthKitAvailable() else {
            isAuthorized = false
            errorMessage = "Health data is not available on this device"
            return
        }
        
        let status = getCurrentAuthorizationStatus()
        print("🔍 HealthKit status check: \(status.rawValue)")
        
        switch status {
        case .sharingAuthorized:
            print("✅ HealthKit is authorized")
            isAuthorized = true
            errorMessage = nil
        case .sharingDenied:
            print("❌ HealthKit is denied")
            isAuthorized = false
            errorMessage = "HealthKit access has been denied. Please enable it in Settings > Privacy & Security > Health > Data Access & Devices > Zivohealth"
        case .notDetermined:
            print("❓ HealthKit status not determined")
            isAuthorized = false
            errorMessage = nil
        @unknown default:
            print("❓ HealthKit status unknown")
            isAuthorized = false
            errorMessage = "Unknown HealthKit authorization status"
        }
    }
    
    /// Refresh authorization status - call this when app becomes active
    func refreshAuthorizationStatus() {
        checkAuthorizationStatus()
    }
    
    /// Show alert with error message
    func showAlert(_ message: String) {
        alertMessage = message
        showingAlert = true
    }
    
    /// Clear error state
    func clearError() {
        errorMessage = nil
        showingAlert = false
        alertMessage = ""
    }
}

// MARK: - SwiftUI Alert Helper
extension HealthKitAuthorizationService {
    func alertView() -> some View {
        EmptyView()
            .alert("HealthKit Authorization", isPresented: Binding(
                get: { [self] in showingAlert },
                set: { [self] in showingAlert = $0 }
            )) {
                Button("OK") {
                    self.clearError()
                }
                
                // Show "Go to Settings" button only when access is denied
                if alertMessage.contains("denied") || alertMessage.contains("Settings") {
                    Button("Go to Settings") {
                        self.openSettings()
                    }
                }
            } message: {
                Text(alertMessage)
            }
    }
    
    private func openSettings() {
        // Open iOS Settings to Privacy & Security > Health > Zivohealth
        if let settingsUrl = URL(string: "App-Prefs:root=Privacy&path=HEALTH") {
            if UIApplication.shared.canOpenURL(settingsUrl) {
                UIApplication.shared.open(settingsUrl)
            } else {
                // Fallback to general Settings if the specific URL doesn't work
                if let generalSettingsUrl = URL(string: "App-Prefs:root=General") {
                    UIApplication.shared.open(generalSettingsUrl)
                }
            }
        }
        clearError()
    }
}
