import SwiftUI

@available(iOS 16.0, *)
struct ManageNutritionPlansView: View {
    @StateObject private var goalsManager = NutritionGoalsManager.shared
    @State private var showingDeleteConfirmation = false
    @State private var showingActivateConfirmation = false
    @State private var goalToDelete: NutritionGoal?
    @State private var goalToActivate: NutritionGoal?

    var body: some View {
        List {
            Section(header: Text("Active")) {
                if let active = goalsManager.activeGoalSummary?.goal {
                    planRow(goal: active, isActive: true)
                } else {
                    Text("No active plan").foregroundColor(.secondary)
                }
            }

            Section(header: Text("Inactive")) {
                if goalsManager.allGoals.filter({ $0.status != "active" }).isEmpty {
                    Text("No previous plans").foregroundColor(.secondary)
                } else {
                    ForEach(goalsManager.allGoals.filter { $0.status != "active" }) { g in
                        planRow(goal: g, isActive: false)
                    }
                }
            }
        }
        .navigationTitle("Manage Plans")
        .onAppear {
            goalsManager.loadActiveGoalSummary()
            goalsManager.loadAllGoals()
        }
        .confirmationDialog("Activate Plan", isPresented: $showingActivateConfirmation) {
            Button("Activate") {
                if let goal = goalToActivate {
                    print("🔵 [ManageNutritionPlansView] CONFIRMED ACTIVATE for goal \(goal.id)")
                    goalsManager.activateGoal(goalId: goal.id) { success in
                        print("🔵 [ManageNutritionPlansView] Activate completion: \(success)")
                        goalsManager.loadActiveGoalSummary()
                        goalsManager.loadAllGoals()
                    }
                }
            }
            Button("Cancel", role: .cancel) { }
        } message: {
            if let goal = goalToActivate {
                Text("Are you sure you want to activate '\(goal.goalName)'? This will deactivate your current plan.")
            }
        }
        .confirmationDialog("Delete Plan", isPresented: $showingDeleteConfirmation) {
            Button("Delete", role: .destructive) {
                if let goal = goalToDelete {
                    print("🔴 [ManageNutritionPlansView] CONFIRMED DELETE for goal \(goal.id)")
                    goalsManager.deleteGoal(goalId: goal.id) { success in
                        print("🔴 [ManageNutritionPlansView] Delete completion: \(success)")
                        goalsManager.loadAllGoals()
                    }
                }
            }
            Button("Cancel", role: .cancel) { }
        } message: {
            if let goal = goalToDelete {
                Text("Are you sure you want to delete '\(goal.goalName)'? This action cannot be undone.")
            }
        }
    }

    @ViewBuilder
    private func planRow(goal: NutritionGoal, isActive: Bool) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Text(goal.goalName).font(.subheadline).fontWeight(.semibold)
                    if isActive {
                        Text("Active").font(.caption2).padding(.horizontal, 6).padding(.vertical, 2)
                            .background(Color.green.opacity(0.15)).foregroundColor(.green).cornerRadius(4)
                    }
                }
                if let d = goal.effectiveAt as Date? {
                    Text("Start: \(d.formatted(date: .abbreviated, time: .omitted))")
                        .font(.caption2).foregroundColor(.secondary)
                }
            }
            Spacer()
            if !isActive {
                HStack(spacing: 8) {
                    Button("Activate") {
                        print("🔵 [ManageNutritionPlansView] ACTIVATE button pressed for goal \(goal.id)")
                        goalToActivate = goal
                        showingActivateConfirmation = true
                    }
                    .font(.caption)
                    .padding(.horizontal, 12).padding(.vertical, 6)
                    .background(Color.blue.opacity(0.12)).foregroundColor(.blue)
                    .cornerRadius(8)
                    .buttonStyle(.plain)

                    Button(role: .destructive) {
                        print("🔴 [ManageNutritionPlansView] DELETE button pressed for goal \(goal.id)")
                        goalToDelete = goal
                        showingDeleteConfirmation = true
                    } label: {
                        Text("Delete")
                    }
                    .font(.caption)
                    .padding(.horizontal, 12).padding(.vertical, 6)
                    .background(Color.red.opacity(0.1)).foregroundColor(.red)
                    .cornerRadius(8)
                    .buttonStyle(.plain)
                }
            }
        }
        .contentShape(Rectangle())
        .onTapGesture {
            // Prevent the entire row from being tappable
            print("📱 [ManageNutritionPlansView] Row tapped for goal \(goal.id) - ignoring")
        }
    }
}

@available(iOS 16.0, *)
struct ManageNutritionPlansView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            ManageNutritionPlansView()
        }
    }
}


