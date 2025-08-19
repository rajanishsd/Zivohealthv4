import SwiftUI
import UIKit

struct ImagePickerView: UIViewControllerRepresentable {
    @Binding var selectedImage: UIImage?
    @Binding var selectedImageURL: URL?
    @Environment(\.dismiss) private var dismiss
    
    let sourceType: UIImagePickerController.SourceType
    
    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.delegate = context.coordinator
        picker.sourceType = sourceType
        
        if sourceType == .camera {
            picker.cameraDevice = .rear
            picker.cameraCaptureMode = .photo
        }
        
        return picker
    }
    
    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {
        // No updates needed
    }
    
    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }
    
    class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let parent: ImagePickerView
        
        init(_ parent: ImagePickerView) {
            self.parent = parent
        }
        
        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey : Any]) {
            if let image = info[.originalImage] as? UIImage {
                parent.selectedImage = image
                
                // Save image to temporary directory
                if let imageData = image.jpegData(compressionQuality: 0.8) {
                    let tempDir = FileManager.default.temporaryDirectory
                    let filename = "camera_photo_\(UUID().uuidString).jpg"
                    let fileURL = tempDir.appendingPathComponent(filename)
                    
                    do {
                        try imageData.write(to: fileURL)
                        parent.selectedImageURL = fileURL
                    } catch {
                        print("Error saving image: \(error)")
                    }
                }
            }
            parent.dismiss()
        }
        
        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            parent.dismiss()
        }
    }
} 