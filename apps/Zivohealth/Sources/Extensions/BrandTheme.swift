import SwiftUI

public enum BrandTheme {
    public static let brandRedUIColor = UIColor(red: 0.89, green: 0.02, blue: 0.07, alpha: 1.0)
}

public extension Font {
    static func brandHeading(_ size: CGFloat = 26, weight: Font.Weight = .bold) -> Font {
        .system(size: size, weight: weight)
    }

    static var brandBody: Font { .system(size: 16) }
    static var brandFootnote: Font { .footnote }
}

public struct BrandPrimaryButtonStyle: ButtonStyle {
    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .font(.brandBody.weight(.semibold))
            .foregroundColor(.white)
            .background(Color.zivoRed)
            .opacity(configuration.isPressed ? 0.8 : 1.0)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}


