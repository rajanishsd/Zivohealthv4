import SwiftUI

struct PrivacyPolicyView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Privacy Policy for ZivoHealth")
                    .font(.title)
                    .fontWeight(.bold)
                    .padding(.bottom, 4)
                
                Text("Last updated: October 17, 2025")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                Divider()
                
                // Section 1
                sectionHeader("1. Introduction")
                sectionText("""
Welcome to ZivoHealth, an iOS mobile application that helps you manage your nutrition, track your vitals, monitor well-being, and receive personalized AI-driven health insights.

This Privacy Policy explains how ZivoHealth ("we", "us", or "our") collects, uses, and protects your information.

By using ZivoHealth, you agree to the collection and use of information in accordance with this policy.
""")
                
                // Section 2
                sectionHeader("2. Information I Collect")
                
                sectionSubheader("A. Information You Provide")
                sectionText("""
When using ZivoHealth, you may voluntarily provide:

• Profile information: name, gender, age, height, and weight.
• Nutrition logs: meals, portions, calories, and macro/micronutrients.
• Vitals and wellness data: heart rate, sleep, steps, SpO₂ (oxygen saturation), blood sugar (glucose), blood pressure, and body weight.
• Mood and emotional state: self-logged wellness or symptoms.
• Prescriptions: medication names, dosages, and schedules.
• Appointments and AI chats: interactions with your nutritionist or AI coach.
• Contact details: email or phone number for support or inquiries.

All data is collected only with your explicit consent and used solely for wellness and personalization.
""")
                
                sectionSubheader("B. Apple Health (HealthKit) Data")
                sectionText("""
If you connect Apple Health (HealthKit), ZivoHealth may read certain categories of data such as:

• Steps and activity
• Calories burned
• Heart rate
• Sleep duration
• SpO₂ (oxygen saturation)
• Blood sugar (glucose)
• Weight and BMI

HealthKit data handling principles:

• Data is used only to display insights, generate recommendations, and track progress.
• Health data is synced to our secure cloud servers and encrypted end-to-end during transmission and storage.
• Health data is never sold, shared, or used for marketing or advertising.
• You can revoke access anytime by going to Profile → Connected devices in the app, or through iOS Settings → Health → Data Access & Devices.

ZivoHealth fully complies with Apple's HealthKit and App Store privacy guidelines.
""")
                
                sectionSubheader("C. Automatically Collected Data")
                sectionText("""
To improve app performance and experience, ZivoHealth may collect:

• Device information (model, iOS version, language, region).
• Crash logs and diagnostics (via Apple's system tools).
• Anonymous feature usage metrics (e.g., session counts).

No advertising identifiers (IDFA) are collected or used.
""")
                
                // Section 3
                sectionHeader("3. How Your Data Is Used")
                sectionText("""
Your data helps ZivoHealth:

• Display your personalized nutrition and wellness dashboard.
• Generate your Health Score based on vitals and logs.
• Provide AI-based nutrition and lifestyle recommendations.
• Track long-term trends like blood sugar stability or oxygen variation.
• Manage nutritionist appointments and chat interactions.
• Enhance app performance and reliability.

ZivoHealth does not sell or share your data for advertising or marketing purposes.
""")
                
                // Section 4
                sectionHeader("4. Data Security and Storage")
                sectionText("""
• Data is securely stored using Apple's Keychain, on-device storage, and encrypted cloud databases (e.g., Firebase, AWS).
• All data transmissions are encrypted via HTTPS/TLS.
• HealthKit data is synced to our secure cloud servers and encrypted both in transit and at rest.
• Only authorized app functions can access your information.

Despite these protections, no method is completely immune to breaches, and you use the app at your own discretion.
""")
                
                // Section 5
                sectionHeader("5. Data Sharing")
                sectionText("""
ZivoHealth may share limited data only:

• With trusted service providers (for hosting, analytics, or messaging) who comply with strict privacy terms.
• When required by law, subpoena, or regulatory authority.
• To prevent fraud or abuse of the service.

No health, SpO₂, or blood sugar data is ever shared for marketing or profiling.
""")
                
                // Section 6
                sectionHeader("6. Data Retention and Deletion")
                sectionText("""
• Your data is retained only as long as you use ZivoHealth or as legally required.

You can delete your account and data by:
• Going to Profile → Delete account in the app.
• Emailing contactus@zivohealth.ai to request full deletion.

Account deletion can be revoked within 7 days by logging back into the app. After 7 days, all data will be permanently deleted from our servers.

Deleting the app will remove all local data from your device but will not delete your account from our servers.
""")
                
                // Section 7
                sectionHeader("7. Your Privacy Rights")
                sectionText("""
You have the right to:

• Access and review your data.
• Correct or update information.
• Withdraw consent for specific data uses.
• Request deletion of your data.
• Export your data (where technically feasible).

To exercise any right, contact contactus@zivohealth.ai.
""")
                
                // Section 8
                sectionHeader("8. Children's Privacy")
                sectionText("""
• ZivoHealth is primarily intended for users 18 years and older.
• Parents or legal guardians may register and use the app on behalf of minors under their care.
• By registering for a minor, guardians confirm they have the authority to provide consent for data collection and use.
• We assume that any account registered for a person under 18 is managed by a parent or legal guardian.
• If you are under 18, please ensure your parent or guardian has reviewed this Privacy Policy and consented to your use of ZivoHealth.
""")
                
                // Section 9
                sectionHeader("9. Health Disclaimer")
                sectionText("""
• ZivoHealth provides wellness and nutritional guidance only.
• It is not a medical device and does not replace professional diagnosis or treatment.
• Always consult a healthcare professional for medical advice, especially regarding conditions like blood sugar or oxygen saturation.
""")
                
                // Section 10
                sectionHeader("10. Changes to This Policy")
                sectionText("""
• This Privacy Policy may be updated occasionally.
• You'll be notified of significant updates through in-app alerts or App Store release notes.

Last updated: October 17, 2025.
""")
                
                // Section 11
                sectionHeader("11. Contact")
                sectionText("""
If you have any questions about privacy or data usage, please reach out:

Company: ZivoHealth
📧 contactus@zivohealth.ai
📍 Bangalore, Karnataka, India
""")
            }
            .padding()
        }
        .navigationTitle("Privacy Policy")
        .navigationBarTitleDisplayMode(.inline)
    }
    
    private func sectionHeader(_ text: String) -> some View {
        Text(text)
            .font(.headline)
            .fontWeight(.semibold)
            .padding(.top, 8)
    }
    
    private func sectionSubheader(_ text: String) -> some View {
        Text(text)
            .font(.subheadline)
            .fontWeight(.semibold)
            .padding(.top, 4)
    }
    
    private func sectionText(_ text: String) -> some View {
        Text(text)
            .font(.body)
            .foregroundColor(.primary)
            .fixedSize(horizontal: false, vertical: true)
    }
}

#Preview {
    NavigationView {
        PrivacyPolicyView()
    }
}

