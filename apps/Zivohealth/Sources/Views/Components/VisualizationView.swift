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
        guard !visualization.relativeUrl.isEmpty else {
            hasError = true
            isLoading = false
            return
        }
        
        // Construct full URL
        let fullURL = networkService.fullURL(for: visualization.relativeUrl)
        
        guard let url = URL(string: fullURL) else {
            hasError = true
            isLoading = false
            return
        }

        
        // Load image asynchronously
        URLSession.shared.dataTask(with: url) { data, response, error in
            DispatchQueue.main.async {
                isLoading = false
                
                if let error = error {
                    print("❌ [VisualizationView] Error loading image: \(error)")
                    hasError = true
                    return
                }
                
                guard let data = data, let loadedImage = UIImage(data: data) else {
                    print("❌ [VisualizationView] Failed to create image from data")
                    hasError = true
                    return
                }
                
                print("✅ [VisualizationView] Successfully loaded image: \(visualization.title)")
                image = loadedImage
            }
        }.resume()
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

#Preview {
    VisualizationView(
        visualization: Visualization(
            id: "sample-viz",
            type: "chart",
            title: "Lab Results Trend",
            description: "Trend analysis of liver function tests over the past 6 months",
            relativeUrl: "/api/v1/files/plots/sample_chart.png",
            metadata: [
                "format": AnyCodable("png"),
                "data_points": AnyCodable(15),
                "size_bytes": AnyCodable(25600)
            ]
        ),
        networkService: NetworkService.shared
    )
    .padding()
}