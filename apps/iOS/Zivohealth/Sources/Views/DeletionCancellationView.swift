import SwiftUI

struct DeletionCancellationView: View {
    let message: String
    @Binding var isPresented: Bool
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 48))
                .foregroundColor(.green)
            
            Text("Account Restored")
                .font(.title2)
                .fontWeight(.bold)
            
            Text(message)
                .font(.body)
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
            
            Button("OK") {
                isPresented = false
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
        }
        .padding(24)
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(radius: 10)
    }
}

#Preview {
    DeletionCancellationView(
        message: "Your account deletion has been cancelled. Welcome back!",
        isPresented: .constant(true)
    )
}
