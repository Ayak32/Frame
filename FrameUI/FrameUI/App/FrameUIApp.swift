//
//  FrameUIApp.swift
//  FrameUI
//
//  Created by Aya Kasim on 3/25/26.
//

import SwiftUI
import SwiftData

@main
struct FrameUIApp: App {
    @StateObject private var tourSession = TourSession()
    
    var body: some Scene {
        WindowGroup {
            NavigationStack {
                TourRequestView()
            }
            .environmentObject(tourSession)
        }
    }
}
