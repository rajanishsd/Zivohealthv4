import Foundation
import UIKit

final class FeedbackReporter {
    static let shared = FeedbackReporter()

    struct UploadURLResponse: Decodable { let uploadUrl: String; let s3Key: String }

    func report(image: UIImage, category: String?, description: String?, route: String?) async throws {
        guard let jpegData = image.jpegData(compressionQuality: 0.85) else { throw NSError(domain: "feedback", code: 0) }
        let upload = try await requestUploadURL(contentType: "image/jpeg")
        try await uploadToS3(uploadUrl: upload.uploadUrl, data: jpegData, contentType: "image/jpeg")
        try await createFeedbackRecord(s3Key: upload.s3Key, category: category, description: description, route: route)
    }

    private func requestUploadURL(contentType: String) async throws -> UploadURLResponse {
        let urlStr = NetworkService.shared.fullURL(for: "/feedback/screenshot/upload-url")
        var req = URLRequest(url: URL(string: urlStr)!)
        req.httpMethod = "POST"
        for (k, v) in NetworkService.shared.authHeaders(requiresAuth: true, body: nil) { req.setValue(v, forHTTPHeaderField: k) }
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONSerialization.data(withJSONObject: ["contentType": contentType])
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else { throw NSError(domain: "feedback", code: 1) }
        return try JSONDecoder().decode(UploadURLResponse.self, from: data)
    }

    private func uploadToS3(uploadUrl: String, data: Data, contentType: String) async throws {
        var req = URLRequest(url: URL(string: uploadUrl)!)
        req.httpMethod = "PUT"
        req.setValue(contentType, forHTTPHeaderField: "Content-Type")
        let (_, resp) = try await URLSession.shared.upload(for: req, from: data)
        guard let http = resp as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NSError(domain: "feedback", code: 2) }
    }

    private func createFeedbackRecord(s3Key: String, category: String?, description: String?, route: String?) async throws {
        let urlStr = NetworkService.shared.fullURL(for: "/feedback")
        var req = URLRequest(url: URL(string: urlStr)!)
        req.httpMethod = "POST"
        for (k, v) in NetworkService.shared.authHeaders(requiresAuth: true, body: nil) { req.setValue(v, forHTTPHeaderField: k) }
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let device = UIDevice.current
        let bundleId = Bundle.main.bundleIdentifier ?? "unknown.bundle"
        let payload: [String: Any] = [
            "s3_key": s3Key,
            "category": category ?? "General",
            "description": description ?? "",
            "route": route ?? "",
            "app_version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "",
            "build_number": Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "",
            "platform": "iOS",
            "os_version": device.systemVersion,
            "device_model": device.model,
            "app_identifier": bundleId
        ]
        req.httpBody = try JSONSerialization.data(withJSONObject: payload)
        let (_, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else { throw NSError(domain: "feedback", code: 3) }
    }
}

enum ScreenCapture {
    static func captureCurrentWindow() -> UIImage? {
        guard let window = UIApplication.shared.connectedScenes
            .compactMap({ $0 as? UIWindowScene })
            .flatMap({ $0.windows })
            .first(where: { $0.isKeyWindow }) else { return nil }
        let format = UIGraphicsImageRendererFormat()
        format.scale = UIScreen.main.scale
        let renderer = UIGraphicsImageRenderer(size: window.bounds.size, format: format)
        return renderer.image { _ in window.drawHierarchy(in: window.bounds, afterScreenUpdates: false) }
    }
}


