import SwiftUI

struct ReportIssueSheet: View {
    let image: UIImage
    var onSubmit: (_ category: String?, _ description: String?) async throws -> Void
    @Environment(\.dismiss) private var dismiss

    private let categories: [String] = [
        "Bug", "Suggestions", "Crash", "UI", "Performance", "Data Issue", "Feature Request", "Other"
    ]
    @State private var category: String = "Bug"
    @State private var description: String = ""
    @State private var isSubmitting = false
    @State private var error: String?
    @State private var showSuccess = false

    var body: some View {
        NavigationView {
            VStack(spacing: 16) {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFit()
                    .cornerRadius(12)
                    .padding(.horizontal)

                VStack(alignment: .leading, spacing: 8) {
                    Picker("Category", selection: $category) {
                        ForEach(categories, id: \.self) { cat in
                            Text(cat).tag(cat)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: .infinity, alignment: .leading)

                    Text("Describe what happened:")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    TextEditor(text: $description)
                        .frame(minHeight: 90)
                        .overlay(
                            RoundedRectangle(cornerRadius: 6)
                                .stroke(Color(.systemGray4), lineWidth: 1)
                        )
                }
                .padding(.horizontal)

                if let err = error {
                    Text(err).foregroundColor(.red).font(.footnote)
                }

                Spacer()

                Button(action: {
                    guard !isSubmitting else { return }
                    isSubmitting = true
                    Task {
                        defer { isSubmitting = false }
                        do {
                            try await onSubmit(category.isEmpty ? nil : category, description.isEmpty ? nil : description)
                            showSuccess = true
                        } catch {
                            self.error = (error as NSError).localizedDescription
                        }
                    }
                }) {
                    HStack {
                        if isSubmitting { ProgressView() } else { Image(systemName: "square.and.arrow.up") }
                        Text(isSubmitting ? "Submitting..." : "Submit")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .padding()
            }
            .navigationTitle("Report an Issue")
            .toolbar(content: {
                ToolbarItemGroup(placement: .navigationBarLeading) {
                    Button("Close") { dismiss() }
                }
            })
            .alert("Thanks!", isPresented: $showSuccess) {
                Button("OK") { dismiss() }
            } message: {
                Text("Your feedback has been submitted.")
            }
        }
    }
}


