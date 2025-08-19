import SwiftUI

struct ContentView: View {
    @State private var selectedTab = 0
    @AppStorage("doctorAuthToken") private var doctorAuthToken = ""
    @AppStorage("userMode") private var userMode: UserMode = .doctor

    var body: some View {
        Group {
            if doctorAuthToken.isEmpty && userMode == .doctor {
                // Root-auth flow
                if #available(iOS 16.0, *) {
                    NavigationStack {
                        DoctorLoginView {
                            // on success, token is stored and this view will re-evaluate
                        }
                    }
                } else {
                    NavigationView {
                        DoctorLoginView {
                            // on success
                        }
                    }
                }
            } else {
                if #available(iOS 16.0, *) {
                    NavigationStack {
                        TabView(selection: $selectedTab) {
                            DoctorDashboardView(onSwitchRole: {})
                                .tabItem { Label("Dashboard", systemImage: "stethoscope") }
                                .tag(0)
                            AppointmentsView()
                                .tabItem { Label("Appointments", systemImage: "calendar") }
                                .tag(1)
                            SettingsView()
                                .tabItem { Label("Settings", systemImage: "gear") }
                                .tag(2)
                        }
                        .onAppear { selectedTab = 0 }
                    }
                } else {
                    NavigationView {
                        TabView(selection: $selectedTab) {
                            DoctorDashboardView(onSwitchRole: {})
                                .tabItem { Label("Dashboard", systemImage: "stethoscope") }
                                .tag(0)
                            AppointmentsView()
                                .tabItem { Label("Appointments", systemImage: "calendar") }
                                .tag(1)
                            SettingsView()
                                .tabItem { Label("Settings", systemImage: "gear") }
                                .tag(2)
                        }
                        .onAppear { selectedTab = 0 }
                        .navigationViewStyle(.stack)
                    }
                }
            }
        }
        .tint(.zivoRed)
    }
}

#Preview {
    ContentView()
}
