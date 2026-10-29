import SwiftUI

@main
struct ProbeApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

struct ContentView: View {
    @State private var tapCount = 0
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "iphone.gen3")
                .font(.system(size: 64))
                .foregroundStyle(.tint)
            Text("Probe Build \(tapCount)")
                .font(.title2.bold())
            Button("Tap me") { tapCount += 1 }
                .buttonStyle(.borderedProminent)
            Text("Built on mac mini, India")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding()
    }
}
