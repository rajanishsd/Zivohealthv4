# Meal Type Grouping - Quick Reference Guide

## Feature Overview
The meals display now uses a **two-layer card system** that groups meals by type (Breakfast, Lunch, Dinner, Snack) with **aggregated nutrition data**.

## Visual Structure

```
┌─────────────────────────────────────────┐
│        NUTRITION VIEW (Main)            │
├─────────────────────────────────────────┤
│  Today's Meals by Type                  │
│  ┌───────────────────────────────┐      │
│  │ 🍳 Breakfast    [2 meals]     │      │
│  │ 🔥 650 cal                    │      │
│  │ P:25g  C:70g  F:20g  Fiber:8g │◄─────┼── Tap to view detail
│  └───────────────────────────────┘      │
│  ┌───────────────────────────────┐      │
│  │ 🥙 Lunch        [1 meal]      │      │
│  │ 🔥 450 cal                    │      │
│  │ P:30g  C:45g  F:15g  Fiber:6g │      │
│  └───────────────────────────────┘      │
│           [See All] button              │
└─────────────────────────────────────────┘
                    │
                    ▼ Tap "See All"
┌─────────────────────────────────────────┐
│       MEALS LIST VIEW (Page)            │
├─────────────────────────────────────────┤
│  Date Picker: [Oct 23, 2025]           │
│                                         │
│  Meals by Type        Swipe to view ◄─►│
│  ┌─────────────────────────────┐       │
│  │ 🍳  Breakfast                │       │
│  │     2 meals                  │       │
│  │                              │       │
│  │ 🔥 650 calories              │       │
│  │                              │       │
│  │ ┌─────┬─────┬─────┬─────┐   │       │
│  │ │Protein│Carbs│ Fat │Fiber│   │◄────┼── Swipe cards
│  │ │ 25g  │ 70g │ 20g │ 8g  │   │       │
│  │ └─────┴─────┴─────┴─────┘   │       │
│  │                              │       │
│  │  Tap to view details     👆  │       │
│  └─────────────────────────────┘       │
└─────────────────────────────────────────┘
                    │
                    ▼ Tap Card
┌─────────────────────────────────────────┐
│   MEAL TYPE SUMMARY (Detail Sheet)     │
├─────────────────────────────────────────┤
│  🍳 Breakfast                           │
│  2 meals • 650 calories                 │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ 📊 Total Nutrition Summary       │   │
│  ├─────────────────────────────────┤   │
│  │ 🔥 Calories    650  kcal         │   │
│  │ Ⓟ  Protein     25.0 g            │   │
│  │ Ⓒ  Carbs       70.0 g            │   │
│  │ Ⓕ  Fat         20.0 g            │   │
│  │ 🍃 Fiber        8.0 g            │   │
│  │ 🧊 Sugar       12.0 g            │   │
│  │ 💧 Sodium     350  mg            │   │
│  │                                  │   │
│  │ Key Vitamins & Minerals          │   │
│  │ • Vit A  500mcg  • Vit C  45mg  │   │
│  │ • Calcium 200mg  • Iron   5mg   │   │
│  └─────────────────────────────────┘   │
│                                         │
│  Individual Meals (2)                   │
│  ┌─────────────────────────────────┐   │
│  │ 7:30 AM                          │   │
│  │ Oatmeal with berries             │◄──┼── Tap to open
│  │ 350 calories                     │   │    MealDetailView
│  │ P:10g  C:45g  F:8g  📷          │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │ 8:00 AM                          │   │
│  │ Greek yogurt                     │   │
│  │ 300 calories                     │   │
│  │ P:15g  C:25g  F:12g             │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## User Interactions

### Level 1: Page View (Swipeable Cards)
- **Swipe Left/Right**: Navigate between meal types
- **Tap Card**: Open meal type summary
- **Visual**: Full-width cards showing aggregated data

### Level 2: Meal Type Summary
- **Top Section**: Total aggregated nutrition
- **Bottom Section**: List of individual meals
- **Tap Individual Meal**: Opens full meal detail
- **Back Button**: Return to meals list

### Level 3: Meal Detail (Existing)
- Full nutritional breakdown
- Image viewing
- All vitamins & minerals
- Edit options

## Key Features

### ✅ Aggregated Nutrition
- See total calories, macros, vitamins, and minerals for each meal type
- Quick overview of daily distribution

### ✅ Page View Navigation
- Smooth horizontal scrolling
- Full-width cards for better visibility
- Natural swipe gestures

### ✅ Smart Grouping
- Automatic grouping by meal type
- Sorted by typical meal order (Breakfast → Lunch → Dinner → Snack)
- Empty meal types are hidden

### ✅ Responsive Design
- Cards adapt to screen width
- Proper spacing and shadows
- Consistent with Zivo brand design

## Code Usage

### Grouping Meals
```swift
let meals: [NutritionDataResponse] = nutritionManager.todaysMeals
let groups: [MealTypeGroup] = meals.groupedByMealType()
```

### Accessing Aggregated Data
```swift
let breakfastGroup = groups.first(where: { $0.mealType == .breakfast })
print("Total calories: \(breakfastGroup?.totalCalories ?? 0)")
print("Total protein: \(breakfastGroup?.totalProtein ?? 0)g")
```

### Rendering Cards
```swift
ForEach(groups) { group in
    MealTypeCard(group: group) {
        // Handle tap
        selectedGroup = group
        showingSummary = true
    }
}
```

## Testing Checklist

- [ ] Meals group correctly by type
- [ ] Aggregated totals match sum of individual meals
- [ ] Page view scrolls smoothly
- [ ] Tap gestures work on all cards
- [ ] Navigation to meal detail works
- [ ] Empty states show correctly
- [ ] Date picker updates meals
- [ ] Back navigation works properly
- [ ] Sheet presentations are smooth
- [ ] Design matches Zivo brand guidelines

## Benefits

### 📊 Better Data Visualization
Users can quickly see how their nutrition is distributed throughout the day.

### 🎯 Improved Navigation
Fewer taps to find specific meals, with logical grouping.

### 📱 Modern UX
Page view cards provide a contemporary, app-like experience.

### 🔢 Aggregated Insights
Instant totals without manual calculation.

## Support

For issues or questions about this feature, refer to:
- `MEAL_TYPE_GROUPING_FEATURE.md` - Technical documentation
- `NutritionView.swift` - Main implementation
- `MealTypeGroup.swift` - Data model

