import SwiftUI
import UIKit

struct ContentView: View {
    @State private var selectedTab = 0
    @AppStorage("doctorAuthToken") private var doctorAuthToken = ""
    @AppStorage("userMode") private var userMode: UserMode = .doctor
    @State private var showReportSheet = false
    @State private var pendingScreenshot: UIImage? = nil

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
                        .onReceive(NotificationCenter.default.publisher(for: UIApplication.userDidTakeScreenshotNotification)) { _ in
                            if let img = ScreenCapture.captureCurrentWindow() {
                                self.pendingScreenshot = img
                                self.showReportSheet = true
                            }
                        }
                    }
                    .overlay(alignment: .topTrailing) {
                        Button(action: { triggerReport() }) {
                            Image(systemName: "ladybug.fill")
                                .font(.system(size: 14, weight: .bold))
                                .foregroundColor(.white)
                                .padding(8)
                                .background(Color.red)
                                .clipShape(Circle())
                                .shadow(radius: 2)
                        }
                        .padding(.trailing, 8)
                        .padding(.top, 48)
                        .accessibilityLabel("Report an issue")
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
                        .onReceive(NotificationCenter.default.publisher(for: UIApplication.userDidTakeScreenshotNotification)) { _ in
                            if let img = ScreenCapture.captureCurrentWindow() {
                                self.pendingScreenshot = img
                                self.showReportSheet = true
                            }
                        }
                        .overlay(alignment: .topTrailing) {
                            Button(action: { triggerReport() }) {
                                Image(systemName: "ladybug.fill")
                                    .font(.system(size: 14, weight: .bold))
                                    .foregroundColor(.white)
                                    .padding(8)
                                    .background(Color.red)
                                    .clipShape(Circle())
                                    .shadow(radius: 2)
                            }
                            .padding(.trailing, 8)
                            .padding(.top, 48)
                            .accessibilityLabel("Report an issue")
                        }
                    }
                }
            }
        }
        .tint(.zivoRed)
        .sheet(isPresented: $showReportSheet) {
            if let img = pendingScreenshot {
                ReportIssueSheet(image: img) { category, description in
                    try await FeedbackReporter.shared.report(image: img, category: category, description: description, route: nil)
                }
            }
        }
    }
}

extension ContentView {
    private func triggerReport() {
        if let img = ScreenCapture.captureCurrentWindow() {
            self.pendingScreenshot = img
            self.showReportSheet = true
        }
    }
}

#Preview {
    ContentView()
}
