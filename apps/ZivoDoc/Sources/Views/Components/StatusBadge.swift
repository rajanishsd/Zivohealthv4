import SwiftUI

struct StatusBadge: View {
    let status: String
    
    var body: some View {
        Text(status.capitalized)
            .font(.caption)
            .fontWeight(.medium)
            .padding(.horizontal, 8)
            .padding(.vertical, 2)
            .background(backgroundColor)
            .foregroundColor(foregroundColor)
            .cornerRadius(4)
    }
    
    private var backgroundColor: Color {
        switch status.lowercased() {
        case "scheduled":
            return .blue.opacity(0.2)
        case "confirmed":
            return .green.opacity(0.2)
        case "cancelled":
            return .red.opacity(0.2)
        case "completed":
            return .gray.opacity(0.2)
        default:
            return .gray.opacity(0.2)
        }
    }
    
    private var foregroundColor: Color {
        switch status.lowercased() {
        case "scheduled":
            return .blue
        case "confirmed":
            return .green
        case "cancelled":
            return .red
        case "completed":
            return .gray
        default:
            return .gray
        }
    }
} 