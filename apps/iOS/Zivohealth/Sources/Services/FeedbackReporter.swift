import Foundation
import UIKit

@MainActor
final class FeedbackReporter {
    static let shared = FeedbackReporter()

    struct UploadURLResponse: Decodable {
        let uploadUrl: String
        let s3Key: String
    }

    func report(image: UIImage,
                category: String?,
                description: String?,
                route: String?) async throws {
        guard let jpegData = image.jpegData(compressionQuality: 0.85) else {
            throw NSError(domain: "feedback", code: 0, userInfo: [NSLocalizedDescriptionKey: "Failed to encode image"])
        }

        let upload = try await requestUploadURL(contentType: "image/jpeg")
        try await uploadToS3(uploadUrl: upload.uploadUrl, data: jpegData, contentType: "image/jpeg")
        try await createFeedbackRecord(s3Key: upload.s3Key,
                                       category: category,
                                       description: description,
                                       route: route)
    }

    private func requestUploadURL(contentType: String) async throws -> UploadURLResponse {
        let urlStr = NetworkService.shared.fullURL(for: "/feedback/screenshot/upload-url")
        guard let url = URL(string: urlStr) else {
            throw NSError(domain: "feedback", code: 1, userInfo: [NSLocalizedDescriptionKey: "Invalid URL"])
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        let headers = NetworkService.shared.authHeaders(requiresAuth: true, body: nil)
        for (k, v) in headers { req.setValue(v, forHTTPHeaderField: k) }
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = ["contentType": contentType]
        req.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw NSError(domain: "upload-url", code: 2, userInfo: [NSLocalizedDescriptionKey: "Upload URL request failed"])
        }
        return try JSONDecoder().decode(UploadURLResponse.self, from: data)
    }

    private func uploadToS3(uploadUrl: String, data: Data, contentType: String) async throws {
        guard let url = URL(string: uploadUrl) else {
            throw NSError(domain: "feedback", code: 3, userInfo: [NSLocalizedDescriptionKey: "Invalid presigned URL"])
        }
        var req = URLRequest(url: url)
        req.httpMethod = "PUT"
        req.setValue(contentType, forHTTPHeaderField: "Content-Type")
        let (_, resp) = try await URLSession.shared.upload(for: req, from: data)
        guard let http = resp as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw NSError(domain: "feedback", code: 4, userInfo: [NSLocalizedDescriptionKey: "S3 upload failed"])
        }
    }

    private func createFeedbackRecord(s3Key: String,
                                      category: String?,
                                      description: String?,
                                      route: String?) async throws {
        let urlStr = NetworkService.shared.fullURL(for: "/feedback")
        guard let url = URL(string: urlStr) else {
            throw NSError(domain: "feedback", code: 5, userInfo: [NSLocalizedDescriptionKey: "Invalid feedback URL"])
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        let headers = NetworkService.shared.authHeaders(requiresAuth: true, body: nil)
        for (k, v) in headers { req.setValue(v, forHTTPHeaderField: k) }
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
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw NSError(domain: "feedback", code: 6, userInfo: [NSLocalizedDescriptionKey: "Creating feedback failed"])
        }
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
        let image = renderer.image { _ in
            window.drawHierarchy(in: window.bounds, afterScreenUpdates: false)
        }
        return image
    }
}


