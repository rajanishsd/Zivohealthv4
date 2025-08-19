import SwiftUI

struct AttachmentOptionsView: View {
    let onUploadFile: () -> Void
    let onTakePhoto: () -> Void
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        VStack(spacing: 0) {
            // Handle bar for drag gesture
            RoundedRectangle(cornerRadius: 2.5)
                .fill(Color.secondary.opacity(0.3))
                .frame(width: 36, height: 5)
                .padding(.top, 8)
                .padding(.bottom, 20)
            
            VStack(spacing: 12) {
                // Add photos and files option
                Button(action: {
                    dismiss()
                    onUploadFile()
                }) {
                    HStack(spacing: 16) {
                        // Icon background
                        ZStack {
                            RoundedRectangle(cornerRadius: 8)
                                .fill(Color.blue.opacity(0.1))
                                .frame(width: 40, height: 40)
                            
                            Image(systemName: "photo.on.rectangle.angled")
                                .font(.system(size: 18, weight: .medium))
                                .foregroundColor(.blue)
                        }
                        
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Add photos and files")
                                .font(.system(size: 16, weight: .medium))
                                .foregroundColor(.primary)
                            Text("Choose from your photo library or files")
                                .font(.system(size: 14))
                                .foregroundColor(.secondary)
                        }
                        
                        Spacer()
                        
                        Image(systemName: "chevron.right")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(.secondary)
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(Color(UIColor.secondarySystemGroupedBackground))
                    )
                }
                .buttonStyle(PlainButtonStyle())
                
                // Take photo option
                Button(action: {
                    dismiss()
                    onTakePhoto()
                }) {
                    HStack(spacing: 16) {
                        // Icon background
                        ZStack {
                            RoundedRectangle(cornerRadius: 8)
                                .fill(Color.green.opacity(0.1))
                                .frame(width: 40, height: 40)
                            
                            Image(systemName: "camera.fill")
                                .font(.system(size: 18, weight: .medium))
                                .foregroundColor(.green)
                        }
                        
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Take photo")
                                .font(.system(size: 16, weight: .medium))
                                .foregroundColor(.primary)
                            Text("Capture a new photo with your camera")
                                .font(.system(size: 14))
                                .foregroundColor(.secondary)
                        }
                        
                        Spacer()
                        
                        Image(systemName: "chevron.right")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(.secondary)
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(Color(UIColor.secondarySystemGroupedBackground))
                    )
                }
                .buttonStyle(PlainButtonStyle())
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 20)
        }
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color(UIColor.systemGroupedBackground))
                .shadow(color: .black.opacity(0.1), radius: 10, x: 0, y: -2)
        )
        .padding(.horizontal, 16)
    }
}

// iOS 16+ presentation style modifier
@available(iOS 16.0, *)
struct PresentationDetentsModifier: ViewModifier {
    func body(content: Content) -> some View {
        if #available(iOS 16.4, *) {
            content
                .presentationDetents([.height(200)])
                .presentationDragIndicator(.hidden)
                .presentationCornerRadius(16)
        } else {
            content
                .presentationDetents([.height(200)])
                .presentationDragIndicator(.hidden)
        }
    }
}

// Fallback modifier for iOS 15 and below
struct FallbackPresentationModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
    }
}

extension View {
    func attachmentSheetStyle() -> some View {
        if #available(iOS 16.0, *) {
            return self.modifier(PresentationDetentsModifier())
        } else {
            return self.modifier(FallbackPresentationModifier())
        }
    }
} 