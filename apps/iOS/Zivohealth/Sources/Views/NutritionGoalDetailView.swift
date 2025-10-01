import SwiftUI

@available(iOS 16.0, *)
struct NutritionGoalDetailView: View {
    @StateObject private var goalsManager = NutritionGoalsManager.shared
    @State private var showingTimePicker: Bool = false
    @State private var editingReminder: NutritionReminderItem? = nil
    @State private var editTime: Date = Date()

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                if let detail = goalsManager.currentGoalDetail {
                    goalHeader(detail)
                    remindersSection()
                    targetsSection(detail)
                    mealPlanSection(detail)
                } else if goalsManager.isLoading {
                    ProgressView("Loading...").padding(.top, 40)
                } else if let error = goalsManager.errorMessage {
                    Text(error).foregroundColor(.red)
                } else {
                    Text("No goal details available").foregroundColor(.secondary).padding(.top, 40)
                }
            }
            .padding()
        }
        .scrollContentBackground(.hidden)
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Plan Details")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if goalsManager.currentGoalDetail == nil {
                goalsManager.loadCurrentGoalDetail()
            }
            goalsManager.loadInactiveGoals()
            goalsManager.loadAllGoals()
        }
    }


    @ViewBuilder
    private func goalHeader(_ detail: NutritionGoalDetail) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            // Goal title and description
            VStack(alignment: .leading, spacing: 8) {
                Text(detail.goal.goalName)
                    .font(.title3)
                    .fontWeight(.semibold)
                if let desc = detail.goal.goalDescription, !desc.isEmpty {
                    Text(desc)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                HStack(spacing: 12) {
                    Text("Start: \(detail.goal.effectiveAt.formatted(date: .abbreviated, time: .omitted))")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    if let exp = detail.goal.expiresAt {
                        Text("End: \(exp.formatted(date: .abbreviated, time: .omitted))")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
            
            // Action buttons
            HStack(spacing: 8) {
                NavigationLink(destination: ManageNutritionPlansView()) {
                    HStack(spacing: 4) {
                        Image(systemName: "rectangle.stack.badge.person.crop")
                            .font(.caption)
                        Text("Manage Plans")
                            .font(.caption)
                            .fontWeight(.medium)
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.blue.opacity(0.12))
                    .foregroundColor(.blue)
                    .cornerRadius(6)
                }

                NavigationLink(destination: NutritionGoalSetupView()) {
                    HStack(spacing: 4) {
                        Image(systemName: "plus.circle.fill")
                            .font(.caption)
                        Text("Create New Plan")
                            .font(.caption)
                            .fontWeight(.medium)
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.purple.opacity(0.12))
                    .foregroundColor(.purple)
                    .cornerRadius(6)
                }
                Spacer()
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
        .sheet(isPresented: $showingTimePicker) {
            if let editing = editingReminder {
                VStack(spacing: 20) {
                    Text("Edit \(editing.meal.capitalized)")
                        .font(.headline)
                    DatePicker("Time", selection: $editTime, displayedComponents: .hourAndMinute)
                        .datePickerStyle(.wheel)
                    HStack {
                        Button("Cancel") { showingTimePicker = false }
                        Spacer()
                        Button("Save") {
                            let formatter = DateFormatter()
                            formatter.dateFormat = "HH:mm"
                            let hhmm = formatter.string(from: editTime)
                            goalsManager.updateCurrentGoalReminder(meal: editing.meal, timeLocal: hhmm, frequency: nil) { _ in }
                            showingTimePicker = false
                        }
                    }
                    .padding(.top, 8)
                }
                .padding()
                .presentationDetents([.height(280)])
            }
        }
    }

    @ViewBuilder
    private func remindersSection() -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "bell.badge.fill").foregroundColor(.teal)
                Text("Reminders").font(.headline).fontWeight(.semibold)
                Spacer()
                if let tz = goalsManager.currentGoalReminders?.timezone {
                    Text(tz).font(.caption).foregroundColor(.secondary)
                }
            }

            if let items = goalsManager.currentGoalReminders?.items, !items.isEmpty {
                ForEach(items, id: \.externalId) { item in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(item.meal.capitalized)
                                .font(.subheadline)
                                .fontWeight(.medium)
                            if let freq = item.frequency, !freq.isEmpty {
                                Text(freq.capitalized)
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                                    .lineLimit(1)
                            }
                        }
                        Spacer()
                        VStack(alignment: .trailing, spacing: 2) {
                            Text(item.timeLocal)
                                .font(.subheadline)
                            Text(item.status.capitalized)
                                .font(.caption2)
                                .foregroundColor(item.status.lowercased() == "active" ? .green : .secondary)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background((item.status.lowercased() == "active" ? Color.green : Color.gray).opacity(0.12))
                                .cornerRadius(6)
                        }
                    }
                    .contentShape(Rectangle())
                    .onTapGesture {
                        startEditingReminder(item)
                    }
                    if item.externalId != items.last?.externalId {
                        Divider()
                    }
                }
            } else {
                Text("No reminders configured")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 8)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }

    // MARK: - Edit Reminder (SwiftUI Sheet)
    private func startEditingReminder(_ item: NutritionReminderItem) {
        editingReminder = item
        editTime = parseHHMM(item.timeLocal) ?? Date()
        showingTimePicker = true
    }

    @ViewBuilder
    private func targetsSection(_ detail: NutritionGoalDetail) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            // Macronutrients Card
            nutrientCategoryCard(
                title: "Macronutrients",
                icon: "chart.bar.fill",
                color: .blue,
                targets: detail.targets.filter { isMacronutrient($0.nutrient.category) }
            )
            
            // Vitamins Card
            nutrientCategoryCard(
                title: "Vitamins",
                icon: "leaf.fill",
                color: .green,
                targets: detail.targets.filter { isVitamin($0.nutrient.category) }
            )
            
            // Minerals Card
            nutrientCategoryCard(
                title: "Minerals",
                icon: "diamond.fill",
                color: .orange,
                targets: detail.targets.filter { isMineral($0.nutrient.category) }
            )
        }
    }
    
    @ViewBuilder
    private func nutrientCategoryCard(title: String, icon: String, color: Color, targets: [NutritionGoalTarget]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                Text(title)
                    .font(.headline)
                    .fontWeight(.semibold)
                Spacer()
                Text("\(targets.count) targets")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            if targets.isEmpty {
                Text("No \(title.lowercased()) targets set")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 8)
            } else {
                ForEach(targets, id: \.id) { target in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(target.nutrient.displayName)
                                .font(.subheadline)
                                .fontWeight(.medium)
                            Text(formatTargetType(target.targetType))
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                        Text(targetText(target))
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                    if target.id != targets.last?.id {
                        Divider()
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }

    // MARK: - Helper Functions
    
    private func parseHHMM(_ s: String) -> Date? {
        let f = DateFormatter()
        f.dateFormat = "HH:mm"
        return f.date(from: s)
    }

    private func isMacronutrient(_ category: String) -> Bool {
        return category.lowercased() == "macronutrient"
    }
    
    private func isVitamin(_ category: String) -> Bool {
        return category.lowercased() == "vitamin"
    }
    
    private func isMineral(_ category: String) -> Bool {
        return category.lowercased() == "mineral"
    }
    
    private func formatTargetType(_ type: String) -> String {
        switch type {
        case "exact":
            return "Target"
        case "min":
            return "Minimum"
        case "max":
            return "Maximum"
        case "range":
            return "Range"
        default:
            return type.capitalized
        }
    }
    
    private func targetText(_ t: NutritionGoalTarget) -> String {
        switch t.targetType {
        case "exact":
            if let v = t.targetMin { return "\(Int(v))" }
        case "min":
            if let v = t.targetMin { return "≥\(Int(v))" }
        case "max":
            if let v = t.targetMax { return "≤\(Int(v))" }
        case "range":
            if let a = t.targetMin, let b = t.targetMax { return "\(Int(a))-\(Int(b))" }
        default:
            break
        }
        return "--"
    }

    @ViewBuilder
    private func mealPlanSection(_ detail: NutritionGoalDetail) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "fork.knife.circle.fill").foregroundColor(.purple)
                Text("Meal Plan Suggestions")
                    .font(.headline)
                Spacer()
            }
            
            if let mp = detail.mealPlan {
                VStack(spacing: 12) {
                    if let breakfast = mp.breakfast {
                        mealTypeCard(section: breakfast, title: "Breakfast", icon: "sun.max.fill", color: .orange)
                    }
                    if let lunch = mp.lunch {
                        mealTypeCard(section: lunch, title: "Lunch", icon: "sun.max.circle.fill", color: .yellow)
                    }
                    if let dinner = mp.dinner {
                        mealTypeCard(section: dinner, title: "Dinner", icon: "moon.fill", color: .blue)
                    }
                    if let snacks = mp.snacks {
                        mealTypeCard(section: snacks, title: "Snacks", icon: "heart.fill", color: .pink)
                    }
                }
            } else {
                Text("No meal plan available").foregroundColor(.secondary)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }

    @ViewBuilder
    private func mealTypeCard(section: MealPlanSection, title: String, icon: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header with icon and title
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                    .font(.title3)
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                Spacer()
                if let rec = section.recommendedOption { 
                    Text("Recommended: #\(rec+1)")
                        .font(.caption)
                        .foregroundColor(.green)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.green.opacity(0.1))
                        .cornerRadius(6)
                }
            }
            
            // Meal options
            if let options = section.options, !options.isEmpty {
                ForEach(options.prefix(3)) { opt in
                    mealOptionRow(opt)
                    if opt.id != options.prefix(3).last?.id {
                        Divider()
                    }
                }
            } else {
                Text("No options available")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 8)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(10)
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(Color.gray.opacity(0.2), lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.03), radius: 1, x: 0, y: 1)
    }
    
    @ViewBuilder
    private func mealOptionRow(_ opt: MealPlanOption) -> some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 4) {
                Text(opt.name)
                    .font(.subheadline)
                    .fontWeight(.medium)
                if let notes = opt.notes { 
                    Text(notes)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                if let ings = opt.ingredients, !ings.isEmpty {
                    Text(ings.joined(separator: ", "))
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                if let c = opt.calories { 
                    Text("\(c) kcal")
                        .font(.caption)
                        .foregroundColor(.orange)
                        .fontWeight(.medium)
                }
                HStack(spacing: 6) {
                    if let p = opt.proteinG { 
                        Text("P \(Int(p))g")
                            .font(.caption2)
                            .foregroundColor(.red)
                    }
                    if let c = opt.carbsG { 
                        Text("C \(Int(c))g")
                            .font(.caption2)
                            .foregroundColor(.blue)
                    }
                    if let f = opt.fatG { 
                        Text("F \(Int(f))g")
                            .font(.caption2)
                            .foregroundColor(.yellow)
                    }
                    if let fi = opt.fiberG { 
                        Text("Fiber \(Int(fi))g")
                            .font(.caption2)
                            .foregroundColor(.green)
                    }
                }
            }
        }
    }
}

@available(iOS 16.0, *)
struct NutritionGoalDetailView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            NutritionGoalDetailView()
        }
    }
}


