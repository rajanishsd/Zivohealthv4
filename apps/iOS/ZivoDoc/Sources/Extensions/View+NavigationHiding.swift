import SwiftUI

public extension View {
    @ViewBuilder
    func hideNavigationBarCompat() -> some View {
        if #available(iOS 16.0, *) {
            self.toolbar(.hidden, for: .navigationBar)
        } else {
            self.navigationBarHidden(true)
        }
    }
}


