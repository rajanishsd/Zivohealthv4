import SwiftUI

struct TermsOfServiceView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Terms and Conditions")
                    .font(.title)
                    .fontWeight(.bold)
                    .padding(.bottom, 4)

                Text("Last updated: October 19, 2025")
                    .font(.subheadline)
                    .foregroundColor(.secondary)

                Divider()

                sectionHeader("1. Acceptance of Terms")
                sectionText("""
By accessing or using ZivoHealth (the "Platform"), you agree to be bound by these Terms. If you do not agree, do not use the Platform.
""")

                sectionHeader("2. Nature of Services")
                sectionText("""
ZivoHealth provides AI-assisted tools and educational content to help users better understand health concerns. The Platform may analyze user-provided information (e.g., symptoms, vitals, lifestyle inputs) to generate insights and educational materials.
""")

                sectionHeader("3. No Medical Advice")
                sectionText("""
The Platform is for informational and educational purposes only and does not provide medical advice, diagnosis, or treatment. Always seek the advice of a qualified healthcare professional for medical concerns. Use of the Platform does not create a doctor–patient relationship.
""")

                sectionHeader("4. Eligibility and Account")
                sectionText("""
You must be at least 18 years old (or the age of majority in your jurisdiction). You are responsible for safeguarding your account credentials and for all activities that occur under your account.
""")

                sectionHeader("5. User Responsibilities")
                sectionText("""
Provide accurate and truthful information. Do not misuse the Platform, including attempting to interfere with operation or security, reverse engineer, or use it for unlawful purposes.
""")

                sectionHeader("6. Privacy")
                sectionText("""
Your use of the Platform is subject to our Privacy Policy, which explains how we collect, use, and share information. Please review it carefully.
""")

                sectionHeader("7. Payments and In-App Purchases")
                sectionText("""
ZivoHealth does not currently offer in-app purchases or paid subscriptions. If paid features are introduced in the future, updated terms, pricing, and refund policies will be presented at purchase.
""")

                sectionHeader("8. Intellectual Property")
                sectionText("""
The Platform and its content are owned by or licensed to ZivoHealth and protected by applicable laws. You are granted a limited, non-exclusive, non-transferable license to use the Platform for personal, non-commercial purposes.
""")

                sectionHeader("9. User Content and Feedback")
                sectionText("""
You retain ownership of content you submit. You grant ZivoHealth a worldwide, non-exclusive, royalty-free license to use your content to operate and improve the Platform, in accordance with the Privacy Policy. Feedback may be used without restriction or compensation.
""")

                sectionHeader("10. Third-Party Services")
                sectionText("""
The Platform may link to or integrate third-party services. We are not responsible for third-party content, terms, or policies.
""")

                sectionHeader("11. Acceptable Use")
                sectionText("""
You agree not to interfere with the Platform, test vulnerabilities, upload malicious code, or engage in fraudulent, deceptive, or unlawful activities, or violate third-party rights.
""")

                sectionHeader("12. Disclaimers")
                sectionText("""
THE PLATFORM IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, WHETHER EXPRESS OR IMPLIED, INCLUDING IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT.
""")

                sectionHeader("13. Limitation of Liability")
                sectionText("""
To the maximum extent permitted by law, ZivoHealth and its affiliates shall not be liable for any indirect, incidental, special, consequential, exemplary, or punitive damages, or loss of profits, revenue, data, or use. Our aggregate liability shall not exceed the greater of (a) the amount you paid (if any) for accessing the Platform in the 12 months preceding the claim, or (b) USD $100.
""")

                sectionHeader("14. Indemnification")
                sectionText("""
You agree to indemnify and hold harmless ZivoHealth and its affiliates from claims arising out of your use of the Platform or violation of these Terms.
""")

                sectionHeader("15. Suspension and Termination")
                sectionText("""
We may suspend or terminate access if you violate these Terms or for any lawful reason. Certain provisions survive termination.
""")

                sectionHeader("16. Changes")
                sectionText("""
We may modify the Platform and these Terms at any time. Material changes will be communicated (e.g., in-app). Continued use after changes constitutes acceptance.
""")

                sectionHeader("17. Governing Law and Venue")
                sectionText("""
These Terms are governed by the laws of India. Disputes shall be resolved exclusively in the courts located in Bengaluru, Karnataka, India.
""")

                sectionHeader("18. Contact")
                sectionText("""
If you have questions about these Terms, contact: contactus@zivohealth.ai
""")
            }
            .padding()
        }
        .navigationTitle("Terms and Conditions")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func sectionHeader(_ text: String) -> some View {
        Text(text)
            .font(.headline)
            .fontWeight(.semibold)
            .padding(.top, 8)
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
        TermsOfServiceView()
    }
}


