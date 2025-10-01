import SwiftUI
import Foundation

/// A SwiftUI view component for displaying visualizations (charts, plots) in chat messages
struct VisualizationView: View {
    let visualization: Visualization
    let networkService: NetworkService
    
    @State private var image: UIImage?
    @State private var isLoading = true
    @State private var hasError = false
    @State private var showingEnlargedView = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Visualization title
            Text(visualization.title)
                .font(.system(size: UIFont.systemFontSize * 0.9, weight: .semibold)) // Slightly larger than message text
                .foregroundColor(.primary)
            
            // Description if available
            if let description = visualization.description, !description.isEmpty {
                Text(description)
                    .font(.system(size: UIFont.systemFontSize * 0.9)) // Match message text size
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.leading)
            }
            
            // Chart/Image display area
            ZStack {
                if isLoading {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color(.systemGray6))
                        .frame(height: 200)
                        .overlay(
                            VStack(spacing: 8) {
                                ProgressView()
                                    .scaleEffect(1.2)
                                Text("Loading visualization...")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        )
                } else if hasError {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color(.systemGray6))
                        .frame(height: 150)
                        .overlay(
                            VStack(spacing: 8) {
                                Image(systemName: "chart.bar.xaxis")
                                    .font(.title)
                                    .foregroundColor(.secondary)
                                Text("Unable to load chart")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        )
                } else if let image = image {
                    GeometryReader { geometry in
                        Image(uiImage: image)
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                            .background(Color.gray.opacity(0.2))
                            .cornerRadius(8)
                            .frame(maxWidth: geometry.size.width, maxHeight: geometry.size.height)
                            .onTapGesture {
                                showingEnlargedView = true
                            }
                            .overlay(
                                // Add a subtle hint that the image is tappable
                                VStack {
                                    HStack {
                                        Spacer()
                                        Image(systemName: "magnifyingglass")
                                            .font(.caption)
                                            .foregroundColor(.white)
                                            .background(Circle().fill(Color.black.opacity(0.6)).frame(width: 24, height: 24))
                                            .padding(8)
                                    }
                                    Spacer()
                                }
                            )
                    }
                    .frame(height: getOptimalImageHeight(for: image))
                } else {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color(.systemGray6))
                        .frame(height: 150)
                        .overlay(
                            VStack(spacing: 8) {
                                Image(systemName: "photo")
                                    .font(.title)
                                    .foregroundColor(.secondary)
                                Text("No image available")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        )
                }
            }
            
            // Metadata footer (optional)
            if let metadata = visualization.metadata {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Image(systemName: "info.circle")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text("Chart Details")
                            .font(.system(size: UIFont.systemFontSize * 0.65)) // Smaller than message text
                            .foregroundColor(.secondary)
                    }
                    
                    // Display relevant metadata
                    ForEach(Array(metadata.keys.prefix(3)), id: \.self) { key in
                        if let value = metadata[key] {
                            HStack {
                                Text("\(key.capitalized):")
                                    .font(.system(size: UIFont.systemFontSize * 0.6)) // Consistent small font
                                    .foregroundColor(.secondary)
                                Spacer()
                                Text(formatMetadataValue(value))
                                    .font(.system(size: UIFont.systemFontSize * 0.6)) // Consistent small font
                                    .foregroundColor(.primary)
                            }
                        }
                    }
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 6)
                .background(Color(.systemGray6))
                .cornerRadius(6)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: Color.black.opacity(0.05), radius: 2, x: 0, y: 1)
        .onAppear {
            loadVisualization()
        }
        .fullScreenCover(isPresented: $showingEnlargedView) {
            EnlargedVisualizationView(
                image: image,
                title: visualization.title,
                description: visualization.description
            )
        }
    }
    
    private func loadVisualization() {
        // Prefer direct paths from top-level fields or metadata (presigned_url, file_path, s3_uri, plot_path)
        var preferredUrl: URL? = nil
        if let presigned = visualization.presignedUrl, !presigned.isEmpty {
            preferredUrl = URL(string: presigned)
        } else if let direct = visualization.filePath ?? visualization.s3Uri ?? visualization.plotPath ?? visualization.path, !direct.isEmpty {
            if direct.hasPrefix("s3://") {
                preferredUrl = buildPresignRedirectURL(for: direct)
            } else if direct.hasPrefix("http://") || direct.hasPrefix("https://") {
                preferredUrl = URL(string: direct)
            }
        } else if let metadata = visualization.metadata {
            if let path = (metadata["file_path"]?.value as? String)
                ?? (metadata["s3_uri"]?.value as? String)
                ?? (metadata["plot_path"]?.value as? String) {
                if path.hasPrefix("s3://") {
                    preferredUrl = buildPresignRedirectURL(for: path)
                } else if path.hasPrefix("http://") || path.hasPrefix("https://") {
                    preferredUrl = URL(string: path)
                }
            }
        }

        // Fallback to backend-served relative URL
        let resolvedURLString: String
        if let url = preferredUrl?.absoluteString {
            resolvedURLString = url
        } else {
            if let rel = visualization.relativeUrl, !rel.isEmpty {
                resolvedURLString = networkService.fullURL(for: rel)
            } else {
                hasError = true
                isLoading = false
                return
            }
        }

        guard let url = URL(string: resolvedURLString) else {
            hasError = true
            isLoading = false
            return
        }

        
        // Build request - only add auth headers for backend requests, not presigned URLs
        var request = URLRequest(url: url)
        
        // Don't add auth headers for S3 presigned URLs
        if !resolvedURLString.contains("amazonaws.com") && !resolvedURLString.contains("s3.") {
            let headers = networkService.authHeaders(requiresAuth: false, body: nil)
            for (k, v) in headers {
                request.setValue(v, forHTTPHeaderField: k)
            }
        }

        // Load image asynchronously
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                isLoading = false
                
                if let error = error {
                    print("❌ [VisualizationView] Error loading image: \(error)")
                    hasError = true
                    return
                }
                
                guard let data = data else {
                    print("❌ [VisualizationView] No data returned for image request")
                    hasError = true
                    return
                }
                
                // Try to decode image first
                if let loadedImage = UIImage(data: data) {
                    print("✅ [VisualizationView] Successfully loaded image: \(visualization.title)")
                    image = loadedImage
                    return
                }
                
                // If not an image, try to parse presign JSON { "url": "https://..." }
                if let presign = try? JSONSerialization.jsonObject(with: data, options: []) as? [String: Any],
                   let urlString = presign["url"] as? String,
                   let s3Url = URL(string: urlString) {
                    var s3Req = URLRequest(url: s3Url)
                    // No headers needed for presigned URL
                    URLSession.shared.dataTask(with: s3Req) { s3Data, _, s3Err in
                        DispatchQueue.main.async {
                            if let s3Err = s3Err {
                                print("❌ [VisualizationView] S3 fetch error: \(s3Err)")
                                hasError = true
                                return
                            }
                            guard let s3Data = s3Data, let s3Image = UIImage(data: s3Data) else {
                                print("❌ [VisualizationView] Failed to create image from S3 data")
                                hasError = true
                                return
                            }
                            print("✅ [VisualizationView] Loaded image from presigned URL")
                            image = s3Image
                        }
                    }.resume()
                    return
                }
                
                // Fallback: if S3 returned NoSuchKey for uploads/chat/plots, try uploads/plots
                let statusCode = (response as? HTTPURLResponse)?.statusCode ?? -1
                let bodyPreview = String(data: data.prefix(200), encoding: .utf8) ?? "binary data"
                if statusCode == 404 && bodyPreview.contains("<Code>NoSuchKey</Code>") {
                    // Attempt to extract the missing key from the XML and rebuild an alternate S3 URI
                    if let keyStart = bodyPreview.range(of: "<Key>"),
                       let keyEnd = bodyPreview.range(of: "</Key>") {
                        let missingKey = String(bodyPreview[keyStart.upperBound..<keyEnd.lowerBound])
                        // Swap '/uploads/chat/plots/' -> '/uploads/plots/'
                        let altKey = missingKey.replacingOccurrences(of: "/uploads/chat/plots/", with: "/uploads/plots/")
                        if altKey != missingKey {
                            // Derive bucket from the failed request URL host (e.g., zivohealth-data.s3.amazonaws.com)
                            let failedHost = (response as? HTTPURLResponse)?.url?.host ?? url.host
                            if let failedHost = failedHost,
                               let bucket = failedHost.components(separatedBy: ".s3").first,
                               !bucket.isEmpty {
                                let altS3Uri = "s3://\(bucket)/\(altKey)"
                                if let altPresign = buildPresignRedirectURL(for: altS3Uri) {
                                    var altReq = URLRequest(url: altPresign)
                                    URLSession.shared.dataTask(with: altReq) { altData, _, _ in
                                        DispatchQueue.main.async {
                                            guard let altData = altData,
                                                  let presign = try? JSONSerialization.jsonObject(with: altData, options: []) as? [String: Any],
                                                  let urlString = presign["url"] as? String,
                                                  let s3Url = URL(string: urlString) else {
                                                print("❌ [VisualizationView] Fallback presign failed for alt key: \(altKey)")
                                                hasError = true
                                                return
                                            }
                                            URLSession.shared.dataTask(with: s3Url) { s3Data, _, _ in
                                                DispatchQueue.main.async {
                                                    if let s3Data = s3Data, let s3Image = UIImage(data: s3Data) {
                                                        print("✅ [VisualizationView] Loaded image via fallback alt key")
                                                        image = s3Image
                                                    } else {
                                                        print("❌ [VisualizationView] Fallback S3 image load failed for alt key")
                                                        hasError = true
                                                    }
                                                }
                                            }.resume()
                                        }
                                    }.resume()
                                    return
                                }
                            }
                        }
                    }
                }
                
                print("❌ [VisualizationView] Failed to create image from data. Status: \(statusCode), Body preview: \(bodyPreview)")
                hasError = true
            }
        }.resume()
    }

    // MARK: - Helpers
    private func buildPresignRedirectURL(for imageUrl: String, ts: String? = nil) -> URL? {
        // Use backend presign redirect endpoint and include api_key query (image loaders may ignore headers)
        let encoded = imageUrl.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? imageUrl
        let apiKey = NetworkService.shared.authHeaders(requiresAuth: false)["X-API-Key"] ?? ""
        let keyParam = apiKey.isEmpty ? "" : "&api_key=\(apiKey)"
        let tsVal = ts ?? String(Int(Date().timeIntervalSince1970))
        // URL-based signature: sig = HMAC_SHA256(s3_uri + "." + ts, appSecret)
        let message = "\(imageUrl).\(tsVal)"
        let secret = NetworkService.shared.appSecretForSigning()
        let sig = NetworkService.shared.hmacSHA256Hex(message: message, secret: secret)
        let pathWithQuery = "/files/s3presign?s3_uri=\(encoded)\(keyParam)&ts=\(tsVal)&sig=\(sig)&format=url"
        let urlStr = NetworkService.shared.fullURL(for: pathWithQuery)
        return URL(string: urlStr)
    }
    
    private func formatMetadataValue(_ value: AnyCodable) -> String {
        if let stringValue = value.value as? String {
            return stringValue
        } else if let intValue = value.value as? Int {
            return "\(intValue)"
        } else if let doubleValue = value.value as? Double {
            return String(format: "%.1f", doubleValue)
        } else if let boolValue = value.value as? Bool {
            return boolValue ? "Yes" : "No"
        } else {
            return "N/A"
        }
    }
    
    private func getOptimalImageHeight(for image: UIImage) -> CGFloat {
        let screenWidth = UIScreen.main.bounds.width - 64 // Account for message padding
        let aspectRatio = image.size.height / image.size.width
        let calculatedHeight = screenWidth * aspectRatio
        
        // Constrain height to reasonable bounds
        return min(max(calculatedHeight, 150), 350)
    }
}

/// Full-screen enlarged view for visualizations
struct EnlargedVisualizationView: View {
    let image: UIImage?
    let title: String
    let description: String?
    
    @Environment(\.dismiss) private var dismiss
    @State private var scale: CGFloat = 1.0
    @State private var offset: CGSize = .zero
    @State private var lastScaleValue: CGFloat = 1.0
    
    var body: some View {
        NavigationView {
            ZStack {
                Color.black.ignoresSafeArea()
                
                if let image = image {
                    GeometryReader { geometry in
                        Image(uiImage: image)
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                            .background(Color.gray.opacity(0.2))
                            .cornerRadius(8)
                            .scaleEffect(scale)
                            .offset(offset)
                            .gesture(
                                SimultaneousGesture(
                                    MagnificationGesture()
                                        .onChanged { value in
                                            let delta = value / lastScaleValue
                                            lastScaleValue = value
                                            let newScale = scale * delta
                                            scale = min(max(newScale, 0.5), 4.0)
                                        }
                                        .onEnded { _ in
                                            lastScaleValue = 1.0
                                            if scale < 1.0 {
                                                withAnimation(.spring()) {
                                                    scale = 1.0
                                                    offset = .zero
                                                }
                                            }
                                        },
                                    
                                    DragGesture()
                                        .onChanged { value in
                                            if scale > 1.0 {
                                                offset = value.translation
                                            }
                                        }
                                        .onEnded { _ in
                                            if scale <= 1.0 {
                                                withAnimation(.spring()) {
                                                    offset = .zero
                                                }
                                            }
                                        }
                                )
                            )
                            .onTapGesture(count: 2) {
                                withAnimation(.spring()) {
                                    if scale == 1.0 {
                                        scale = 2.0
                                    } else {
                                        scale = 1.0
                                        offset = .zero
                                    }
                                }
                            }
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                    }
                } else {
                    VStack(spacing: 20) {
                        Image(systemName: "photo")
                            .font(.system(size: 50))
                            .foregroundColor(.gray)
                        Text("Image not available")
                            .font(.title2)
                            .foregroundColor(.white)
                    }
                }
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .navigationBarItems(
                leading: Button("Done") {
                    dismiss()
                }
                .foregroundColor(.white)
            )
            .onAppear {
                // Configure navigation bar appearance for better visibility on dark background
                let appearance = UINavigationBarAppearance()
                appearance.configureWithTransparentBackground()
                appearance.backgroundColor = UIColor.black.withAlphaComponent(0.8)
                appearance.titleTextAttributes = [.foregroundColor: UIColor.white]
                appearance.largeTitleTextAttributes = [.foregroundColor: UIColor.white]
                
                UINavigationBar.appearance().standardAppearance = appearance
                UINavigationBar.appearance().compactAppearance = appearance
                UINavigationBar.appearance().scrollEdgeAppearance = appearance
            }
            .onDisappear {
                // Reset navigation bar appearance when leaving the view
                let defaultAppearance = UINavigationBarAppearance()
                defaultAppearance.configureWithDefaultBackground()
                
                UINavigationBar.appearance().standardAppearance = defaultAppearance
                UINavigationBar.appearance().compactAppearance = defaultAppearance
                UINavigationBar.appearance().scrollEdgeAppearance = defaultAppearance
            }
        }
    }
}

/// Container view for multiple visualizations
struct VisualizationsContainerView: View {
    let visualizations: [Visualization]
    let networkService: NetworkService
    
    var body: some View {
        VStack(spacing: 16) {
            ForEach(visualizations, id: \.id) { visualization in
                VisualizationView(
                    visualization: visualization,
                    networkService: networkService
                )
            }
        }
    }
}

//#Preview {
//    VisualizationView(
//        visualization: Visualization(
//            id: "sample-viz",
//            type: "chart",
//            title: "Lab Results Trend",
//            description: "Trend analysis of liver function tests over the past 6 months",
//            presignedUrl: "https://example.com/presigned.png"
//        ),
//        networkService: NetworkService.shared
//    )
//    .padding()
//}