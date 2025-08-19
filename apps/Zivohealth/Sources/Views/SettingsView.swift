import SwiftUI

struct SettingsView: View {
    @AppStorage("userMode") private var userMode: UserMode = .patient
    @AppStorage("patientAuthToken") private var patientAuthToken = ""
    @AppStorage("doctorAuthToken") private var doctorAuthToken = ""
    @AppStorage("apiEndpoint") private var apiEndpoint = "http://192.168.0.105:8000"
    @State private var showingDeleteAlert = false
    @State private var customEndpoint = ""
    @State private var selectedEndpointType: EndpointType = .local
    @State private var showingCustomEndpointInput = false
    
    enum EndpointType: String, CaseIterable {
        case local = "Local Network"
        case ngrok = "ngrok Tunnel"
        case custom = "Custom URL"
        
        var defaultURL: String {
            switch self {
            case .local:
                return "http://192.168.0.105:8000"
            case .ngrok:
                return "https://your-subdomain.ngrok-free.app"
            case .custom:
                return ""
            }
        }
    }

    var body: some View {
        Form {
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
                    }
                    
                    Button("Update Endpoint") {
                        updateEndpoint()
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(selectedEndpointType == .custom && customEndpoint.isEmpty)
                }
            }
            
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

            Section(header: Text("Actions")) {
                Button("Sign Out") {
                    showingDeleteAlert = true
                }
                .foregroundColor(.red)
                
                Button("Refresh Authentication") {
                    // Clear current token to force re-authentication
                    if userMode == .patient {
                        patientAuthToken = ""
                    } else {
                        doctorAuthToken = ""
                    }
                    
                    // Trigger re-authentication
                    NetworkService.shared.handleRoleChange()
                }
                .foregroundColor(.blue)
            }

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
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            // Empty toolbar to override inherited toolbar items
        }
        .onAppear {
            initializeEndpointType()
            customEndpoint = apiEndpoint
        }
        .alert("Sign Out", isPresented: $showingDeleteAlert) {
            Button("Cancel", role: .cancel) { }
            Button("Sign Out", role: .destructive) {
                // Clear all stored authentication data
                patientAuthToken = ""
                doctorAuthToken = ""
                NetworkService.shared.clearAllTokens()
            }
        } message: {
            Text("This will sign you out of your account. You will need to log in again.")
        }
    }
    
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
        
        // Validate URL format
        guard URL(string: newEndpoint) != nil else {
            return
        }
        
        // Remove trailing slash if present
        let cleanEndpoint = newEndpoint.hasSuffix("/") ? String(newEndpoint.dropLast()) : newEndpoint
        
        apiEndpoint = cleanEndpoint
        
        // Clear tokens since endpoint changed
        patientAuthToken = ""
        doctorAuthToken = ""
        
        // Notify NetworkService of the change
        NetworkService.shared.handleEndpointChange()
    }
}

#Preview {
    SettingsView()
}
