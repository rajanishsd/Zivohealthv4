import SwiftUI

@available(iOS 16.0, *)
struct NutritionGoalSetupView: View {
    @StateObject private var nutritionGoalsManager = NutritionGoalsManager.shared
    @StateObject private var chatViewModel = ChatViewModel.shared
    
    @State private var selectedObjective: NutritionObjective?
    @State private var isLoading = false
    
    @State private var navigateToChat = false
    @State private var pendingDraft: String? = nil
    @State private var pendingPlaceholder: String? = nil
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 24) {
                    // Header
                    VStack(spacing: 8) {
                        Image(systemName: "target")
                            .font(.largeTitle)
                            .foregroundColor(.green)
                        
                        Text("Set Your Nutrition Goal")
                            .font(.title2)
                            .fontWeight(.semibold)
                        
                        Text("Choose an objective that aligns with your health goals")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.top)
                    
                    // Objectives List
                    VStack(spacing: 16) {
                        Text("Select Your Objective")
                            .font(.headline)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        
                        if nutritionGoalsManager.objectives.isEmpty {
                            if nutritionGoalsManager.isLoading {
                                ProgressView("Loading objectives...")
                                    .padding(.vertical, 40)
                            } else {
                                Text("No objectives available")
                                    .foregroundColor(.secondary)
                                    .padding(.vertical, 40)
                            }
                        } else {
                            // Objectives plus a Custom option at the end
                            let objectivesWithCustom = nutritionGoalsManager.objectives + [
                                NutritionObjective(code: "custom", displayName: "Custom", description: "Describe your own nutrition goal")
                            ]
                            ForEach(objectivesWithCustom) { objective in
                                ObjectiveCard(
                                    objective: objective,
                                    isSelected: selectedObjective?.code == objective.code
                                ) {
                                    selectedObjective = objective
                                }
                            }
                        }
                    }
                    
                    Spacer(minLength: 100)
                }
                .padding(.horizontal)
            }
            .navigationTitle("Nutrition Goals")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Continue") {
                        createGoal()
                    }
                    .disabled(selectedObjective == nil || isLoading)
                }
            }
            // Push ChatView as next page in same context with prefilled draft
            .background(
                NavigationLink(
                    destination: ChatView(prefillDraft: pendingDraft, placeholderText: pendingPlaceholder),
                    isActive: $navigateToChat,
                    label: { EmptyView() }
                )
                .hidden()
            )
        }
        .onAppear {
            nutritionGoalsManager.loadObjectives()
        }
    }
    
    private func createGoal() {
        guard let objective = selectedObjective else { return }
        
        isLoading = true
        
        // Prepare prefilled message or placeholder and push ChatView in same navigation stack
        if objective.code == "custom" {
            let message = "I want to start a {define your own nutrition goal} plan. Please set nutrition goals accordingly."
            pendingDraft = message
            pendingPlaceholder = nil
        } else {
            let message = "I want to start a \(objective.displayName) plan. Please set nutrition goals accordingly."
            pendingDraft = message
            pendingPlaceholder = nil
        }
        Task {
            await chatViewModel.createNewSession()
            isLoading = false
            navigateToChat = true
        }
    }
}

@available(iOS 16.0, *)
struct ObjectiveCard: View {
    let objective: NutritionObjective
    let isSelected: Bool
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(objective.displayName)
                            .font(.headline)
                            .fontWeight(.semibold)
                            .foregroundColor(.primary)
                        
                        if let description = objective.description {
                            Text(description)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.leading)
                        }
                    }
                    
                    Spacer()
                    
                    if isSelected {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.title2)
                            .foregroundColor(.green)
                    } else {
                        Image(systemName: "circle")
                            .font(.title2)
                            .foregroundColor(.gray)
                    }
                }
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(isSelected ? Color.green.opacity(0.1) : Color(.systemBackground))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(isSelected ? Color.green : Color.gray.opacity(0.3), lineWidth: isSelected ? 2 : 1)
                    )
            )
        }
        .buttonStyle(PlainButtonStyle())
    }
}

@available(iOS 16.0, *)
#Preview {
    NutritionGoalSetupView()
}
