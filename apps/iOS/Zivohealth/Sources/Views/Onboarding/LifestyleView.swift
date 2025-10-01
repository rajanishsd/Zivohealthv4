import SwiftUI

struct LifestyleView: View {
    @ObservedObject var vm: OnboardingViewModel

    var body: some View {
        Form {
            Toggle("Do you smoke?", isOn: $vm.smokes)
            Toggle("Do you drink alcohol?", isOn: $vm.drinksAlcohol)
            Toggle("Do you do regular exercise?", isOn: $vm.exercisesRegularly)
            if vm.exercisesRegularly {
                Picker("Type", selection: $vm.exerciseType) {
                    Text("Gym").tag("gym")
                    Text("Running").tag("running")
                    Text("Yoga").tag("yoga")
                    Text("Other").tag("other")
                }
                Stepper(value: $vm.exerciseFrequencyPerWeek, in: 0...14) {
                    Text("Frequency: \(vm.exerciseFrequencyPerWeek)x/week")
                }
            }
        }
    }
}


