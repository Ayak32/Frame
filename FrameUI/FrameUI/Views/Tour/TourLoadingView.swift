//
//  TourLoadingView.swift
//  FrameUI
//
//  Created by Aya Kasim on 4/6/26.
//

import SwiftUI

/// Full-screen loading UI while a tour request is in flight (`session.isLoading`).
struct TourLoadingView: View {
    var body: some View {
        ZStack {
            Color("LaunchScreenBackground")
                .ignoresSafeArea()

            VStack(spacing: 28) {
                FrameLoader()
                VStack(spacing: 8) {
                    Text("Framing Your Journey")
                        .font(Font.custom("American Typewriter", size: 22))
                        .multilineTextAlignment(.center)

                    Text("Tour generation may take up to 1-2 minutes depending on tour length.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 32)
                }
            }
        }
        .interactiveDismissDisabled(true)
    }
}

import SwiftUI

struct FrameLoader: View {
    @State private var showTop = false
    @State private var showRight = false
    @State private var showBottom = false
    @State private var showLeft = false

    let frameSize: CGFloat = 160
    let horizontalScale: CGFloat = 1.12
    

    private let fadeDuration: Double = 0.50

    var body: some View {
//        let verticalSeparation: CGFloat = frameSize / 5
        ZStack {
            Image("top_frame")
                .resizable()
                .scaledToFit()
                .frame(width: frameSize * horizontalScale)
                .opacity(showTop ? 1 : 0)
                .animation(.easeInOut(duration: fadeDuration), value: showTop)
                .offset(y: -frameSize / 2.9)
//                .offset(y: -verticalSeparation)
                .zIndex(2)

            Image("right_frame")
                .resizable()
                .scaledToFit()
                .frame(width: frameSize)
                .opacity(showRight ? 1 : 0)
                .animation(.easeInOut(duration: fadeDuration), value: showRight)
                .offset(x: frameSize / 2.8)
                .zIndex(1)

            Image("bottom_frame")
                .resizable()
                .scaledToFit()
                .frame(width: frameSize * horizontalScale)
                .opacity(showBottom ? 1 : 0)
                .animation(.easeInOut(duration: fadeDuration), value: showBottom)
                .offset(y: frameSize / 2.9)
                .zIndex(2)

            Image("left_frame")
                .resizable()
                .scaledToFit()
                .frame(width: frameSize)
                .opacity(showLeft ? 1 : 0)
                .animation(.easeInOut(duration: fadeDuration), value: showLeft)
                .offset(x: -frameSize / 2.8)
                .zIndex(1)
        }
        .frame(width: frameSize + 30, height: frameSize + 30)
        .onAppear {
            startLoop()
        }
    }

    func startLoop() {
        let duration = 0.25
        let delay = 0.1
        let holdAfterComplete = 0.50
        let offGapBetweenCycles = 0.1
        let visiblePhaseEnd = 4 * (duration + delay)
        let total = visiblePhaseEnd + holdAfterComplete + fadeDuration + offGapBetweenCycles

        showTop = false
        showRight = false
        showBottom = false
        showLeft = false

        withAnimation(.easeInOut(duration: fadeDuration)) {
            showTop = true
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + duration + delay) {
            withAnimation(.easeInOut(duration: fadeDuration)) {
                showRight = true
            }
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 2 * (duration + delay)) {
            withAnimation(.easeInOut(duration: fadeDuration)) {
                showBottom = true
            }
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 3 * (duration + delay)) {
            withAnimation(.easeInOut(duration: fadeDuration)) {
                showLeft = true
            }
        }

        // Fade everything out before restarting so `top_frame` visibly disappears then re-appears.
        DispatchQueue.main.asyncAfter(deadline: .now() + visiblePhaseEnd + holdAfterComplete) {
            withAnimation(.easeInOut(duration: fadeDuration)) {
                showTop = false
                showRight = false
                showBottom = false
                showLeft = false
            }
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + total) {
            startLoop()
        }
    }
}


//private struct FrameLoader: View {
//    /// 0 = top, 1 = right, 2 = bottom, 3 = left. Only one is visible; each step replaces the last in the same centered slot.
//    @State private var activeIndex = 0
//    @State private var sequenceTask: Task<Void, Never>?
//
//    private let frameSize: CGFloat = 160
//    /// Match `Task.sleep` spacing so the next step starts after the transition finishes (reduces choppy cuts).
//    private let transitionDuration: TimeInterval = 0.48
//    private let pauseBetweenCycles: TimeInterval = 0.45
//
//    var body: some View {
//        ZStack {
//            piece("frame_top", index: 0)
//            piece("frame_right", index: 1)
//            piece("frame_bottom", index: 2)
//            piece("frame_left", index: 3)
//        }
//        .compositingGroup()
//        .frame(width: frameSize + 30, height: frameSize + 30)
//        .animation(.smooth(duration: transitionDuration, extraBounce: 0), value: activeIndex)
//        .onAppear {
//            startSequence()
//        }
//        .onDisappear {
//            sequenceTask?.cancel()
//            sequenceTask = nil
//        }
//    }
//
//    private func piece(_ name: String, index: Int) -> some View {
//        Image(name)
//            .resizable()
//            .scaledToFit()
//            .frame(width: frameSize, height: frameSize)
//            .opacity(activeIndex == index ? 1 : 0)
//            .zIndex(activeIndex == index ? 1 : 0)
//            .allowsHitTesting(false)
//            .accessibilityHidden(activeIndex != index)
//    }
//
//    private func startSequence() {
//        sequenceTask?.cancel()
//        sequenceTask = Task { @MainActor in
//            await runSequenceLoop()
//        }
//    }
//
//    /// Runs until cancelled. Errors from `Task.sleep` (e.g. cancellation) end the loop — not `throws`, so `Task<Void, Never>` is valid.
//    private func runSequenceLoop() async {
//        while !Task.isCancelled {
//            for i in 0..<4 {
//                activeIndex = i
//                do {
//                    try await sleepNanoseconds(transitionDuration)
//                } catch {
//                    return
//                }
//            }
//            do {
//                try await sleepNanoseconds(pauseBetweenCycles)
//            } catch {
//                return
//            }
//        }
//    }
//
//    private func sleepNanoseconds(_ seconds: TimeInterval) async throws {
//        let ns = UInt64((seconds * 1_000_000_000).rounded())
//        try await Task.sleep(nanoseconds: ns)
//    }
//}

#Preview {
    TourLoadingView()
}
