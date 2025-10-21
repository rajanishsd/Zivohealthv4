import SwiftUI

struct AboutZivoView: View {
    private var appVersion: String {
        let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""
        let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? ""
        return [version, build].filter { !$0.isEmpty }.joined(separator: " (") + (build.isEmpty ? "" : ")")
    }
    
    var body: some View {
        List {
            VStack(spacing: 12) {
                Image("ZivoDocLogo")
                    .resizable()
                    .renderingMode(.original)
                    .scaledToFit()
                    .frame(width: 80, height: 80)
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                
                Text("Zivo Health")
                    .font(.headline)
                Text("Version \(appVersion)")
                    .font(.footnote)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity)
            .listRowBackground(Color.white)
            .listRowSeparator(.hidden)
            
            Section {
                NavigationLink(destination: PrivacyPolicyView()) {
                    HStack(spacing: 12) {
                        Image(systemName: "lock.shield")
                            .foregroundColor(.secondary)
                        Text("Privacy Policy")
                        Spacer()
                    }
                    .padding(.vertical, 6)
                }
                NavigationLink(destination: TermsOfServiceView()) {
                    HStack(spacing: 12) {
                        Image(systemName: "doc.text")
                            .foregroundColor(.secondary)
                        Text("Terms and Conditions")
                        Spacer()
                    }
                    .padding(.vertical, 6)
                }
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle("About Zivo")
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview {
    NavigationView { AboutZivoView() }
}
