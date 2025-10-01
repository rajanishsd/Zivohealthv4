import SwiftUI

struct HealthConditionsView: View {
    @ObservedObject var vm: OnboardingViewModel

    let conditions = ["Diabetes", "Hypertension", "Thyroid issues", "Celiac disease", "Heart disease"]
    let allergies = ["nuts", "gluten", "lactose"]

    var body: some View {
        Form {
            Section(header: Text("Conditions")) {
                ForEach(conditions, id: \.self) { c in
                    Toggle(c, isOn: Binding(
                        get: { vm.selectedConditions.contains(c) },
                        set: { isOn in
                            if isOn {
                                vm.selectedConditions.insert(c)
                            } else {
                                vm.selectedConditions.remove(c)
                            }
                        }
                    ))
                }
                TextField("Other condition", text: $vm.otherConditionText)
            }
            Section(header: Text("Allergies")) {
                ForEach(allergies, id: \.self) { a in
                    Toggle(a, isOn: Binding(
                        get: { vm.selectedAllergies.contains(a) },
                        set: { isOn in
                            if isOn {
                                vm.selectedAllergies.insert(a)
                            } else {
                                vm.selectedAllergies.remove(a)
                            }
                        }
                    ))
                }
                TextField("Other allergy", text: $vm.otherAllergyText)
            }
        }
    }
}


