//
//  ContentView.swift
//  FrameUI
//
//  Created by Aya Kasim on 3/25/26.
//

import SwiftUI

struct ContentView: View {
    var body: some View {
        ZStack() {
            Color(.mint)
            TabView{
                Tab(Constants.tourString, systemImage: "figure.walk"){
                    Text(Constants.tourString)
                }
                Tab(Constants.exploreString, systemImage: "map"){
                    Text(Constants.exploreString)
                }
                
            }
        }
        
        
    }
}

#Preview {
    ContentView()
}
