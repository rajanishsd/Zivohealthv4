import SwiftUI

struct SettingsView: View {
    @AppStorage("userMode") private var userMode: UserMode = .patient
    @AppStorage("patientAuthToken") private var patientAuthToken = ""
    @AppStorage("doctorAuthToken") private var doctorAuthToken = ""
    @AppStorage("patientRefreshToken") private var patientRefreshToken = ""
    @AppStorage("apiEndpoint") private var apiEndpoint = ""
    @State private var showingDeleteAlert = false
    @State private var customEndpoint = ""
    @State private var selectedEndpointType: EndpointType = .local
    @State private var showingCustomEndpointInput = false
    @State private var showingDebugInfo = false
    
    enum EndpointType: String, CaseIterable {
        case local = "Local Network"
        case ngrok = "ngrok Tunnel"
        case custom = "Custom URL"
        
        var defaultURL: String {
            switch self {
            case .local:
                return "http://192.168.0.100:8000"
            case .ngrok:
                return "https://your-subdomain.ngrok-free.app"
            case .custom:
                return ""
            }
        }
    }

    var body: some View {
        NavigationView {
            List {
                apiConfigurationSection()
                quickSetupSection()
                userPreferencesSection()
                actionsSection()
                aboutSection()
                #if DEBUG
                debugSection()
                #endif
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.large)
            .toolbar { }
            .onAppear {
                initializeEndpointType()
                customEndpoint = apiEndpoint
                if apiEndpoint.isEmpty {
                    apiEndpoint = AppConfig.defaultAPIEndpoint
                }
            }
            .alert("Sign Out", isPresented: $showingDeleteAlert) {
                Button("Cancel", role: .cancel) { }
                Button("Sign Out", role: .destructive) {
                    patientAuthToken = ""
                    doctorAuthToken = ""
                    NetworkService.shared.clearAllTokens()
                }
            } message: {
                Text("This will sign you out of your account. You will need to log in again.")
            }
            .alert("Debug Configuration", isPresented: $showingDebugInfo) {
                Button("OK") { }
            } message: {
                Text(AppConfig.debugInfo)
            }
        }
    }
    
    // MARK: - Sections (extracted to help the compiler)
    private func apiConfigurationSection() -> some View {
        Section(header: Text("API Configuration")) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Backend Server")
                    .font(.headline)
                
                Picker("Endpoint Type", selection: $selectedEndpointType) {
                    ForEach(EndpointType.allCases, id: \.self) { type in
                        Text(type.rawValue).tag(type)
                    }
                }
                .pickerStyle(SegmentedPickerStyle())
                
                if selectedEndpointType == .custom {
                    TextField("Enter custom URL", text: $customEndpoint)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                        .keyboardType(.URL)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                }
                
                HStack {
                    Text("Current URL:")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(apiEndpoint)
                        .font(.caption)
                        .foregroundColor(.blue)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
                
                Button("Update Endpoint") {
                    updateEndpoint()
                }
                .buttonStyle(.borderedProminent)
                .disabled(selectedEndpointType == .custom && customEndpoint.isEmpty)
            }
        }
    }
    
    private func quickSetupSection() -> some View {
        Section(header: Text("Quick Setup Instructions")) {
            VStack(alignment: .leading, spacing: 4) {
                Text("For USB Development:")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                Text("1. Install ngrok: brew install ngrok")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text("2. Run: ngrok http 8000")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text("3. Copy the https URL and select 'ngrok Tunnel' above")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
    
    private func userPreferencesSection() -> some View {
        Section(header: Text("User Preferences")) {
            HStack {
                Text("Current Role")
                Spacer()
                Text(userMode == .patient ? "Patient" : "Doctor")
                    .foregroundColor(.secondary)
            }
            
            HStack {
                Text("Authentication Status")
                Spacer()
                let currentToken = userMode == .patient ? patientAuthToken : doctorAuthToken
                Text(currentToken.isEmpty ? "Not Authenticated" : "Authenticated")
                    .foregroundColor(currentToken.isEmpty ? .red : .green)
            }
        }
    }
    
    private func actionsSection() -> some View {
        Section(header: Text("Actions")) {
            Button("Sign Out") {
                showingDeleteAlert = true
            }
            .foregroundColor(.red)
            
            Button("Refresh Authentication") {
                if userMode == .patient {
                    patientAuthToken = ""
                } else {
                    doctorAuthToken = ""
                }
                NetworkService.shared.handleRoleChange()
            }
            .foregroundColor(.blue)
        }
    }
    
    private func aboutSection() -> some View {
        Section(header: Text("About")) {
            HStack {
                Text("App Version")
                Spacer()
                Text("1.0.0")
                    .foregroundColor(.secondary)
            }
            HStack {
                Text("Build")
                Spacer()
                Text("2024.12.10")
                    .foregroundColor(.secondary)
            }
        }
    }
    
    #if DEBUG
    private func debugSection() -> some View {
        Section("🔧 Debug Configuration") {
            VStack(alignment: .leading, spacing: 8) {
                let currentEnv = AppConfig.Environment.current.rawValue.uppercased()
                Text("Current Environment: \(currentEnv)")
                    .font(.headline)
                Text("API Endpoint: \(apiEndpoint)")
                    .font(.subheadline)
                let forceHTTPS = AppConfig.forceHTTPS ? "Yes" : "No"
                Text("Force HTTPS: \(forceHTTPS)")
                    .font(.subheadline)
                let allowLocalIP = AppConfig.allowLocalIP ? "Yes" : "No"
                Text("Allow Local IP: \(allowLocalIP)")
                    .font(.subheadline)
                let buildType = AppConfig.isDebug ? "DEBUG" : "RELEASE"
                Text("Build Type: \(buildType)")
                    .font(.subheadline)
            }
            .padding(.vertical, 4)
            Button("Show Full Debug Info") { showingDebugInfo = true }
                .foregroundColor(.blue)
        }
    }
    #endif
    
    // MARK: - Helpers
    private func initializeEndpointType() {
        if apiEndpoint.contains("ngrok") {
            selectedEndpointType = .ngrok
        } else if apiEndpoint == EndpointType.local.defaultURL {
            selectedEndpointType = .local
        } else {
            selectedEndpointType = .custom
        }
    }
    
    private func updateEndpoint() {
        let newEndpoint: String
        switch selectedEndpointType {
        case .local:
            newEndpoint = EndpointType.local.defaultURL
        case .ngrok:
            newEndpoint = EndpointType.ngrok.defaultURL
        case .custom:
            newEndpoint = customEndpoint.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        guard URL(string: newEndpoint) != nil else { return }
        let cleanEndpoint = newEndpoint.hasSuffix("/") ? String(newEndpoint.dropLast()) : newEndpoint
        apiEndpoint = cleanEndpoint
        patientAuthToken = ""
        doctorAuthToken = ""
        NetworkService.shared.handleEndpointChange()
    }
}

#Preview {
    SettingsView()
}
