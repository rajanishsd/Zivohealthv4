# Meal Type Grouping Feature

## Overview
Implemented a two-layer meal display system that groups meals by meal type (Breakfast, Lunch, Dinner, Snack) with aggregated nutrition data.

## Architecture

### 1. Data Model (`MealTypeGroup.swift`)
- **Location**: `apps/iOS/Zivohealth/Sources/Models/MealTypeGroup.swift`
- **Purpose**: Groups meals by meal type and provides aggregated nutrition calculations
- **Key Features**:
  - Groups meals by `MealType` (breakfast, lunch, dinner, snack, other)
  - Calculates total calories, protein, carbs, fat, fiber, sugar, sodium
  - Aggregates vitamins (A, C, D) and minerals (Calcium, Iron, Magnesium)
  - Extension on `[NutritionDataResponse]` for easy grouping

### 2. Level 1 View - Meal Type Card (`MealTypeCard.swift`)
- **Location**: `apps/iOS/Zivohealth/Sources/Views/MealTypeCard.swift`
- **Purpose**: Top-level card showing aggregated nutrition for a meal type
- **Features**:
  - Displays meal type emoji and name
  - Shows total meal count for the type
  - Highlights total calories prominently
  - Shows macronutrients grid (Protein, Carbs, Fat, Fiber)
  - Tap gesture to view detailed summary

### 3. Level 2 View - Meal Type Summary (`MealTypeSummaryView.swift`)
- **Location**: `apps/iOS/Zivohealth/Sources/Views/MealTypeSummaryView.swift`
- **Purpose**: Detailed view showing all meals within a meal type
- **Features**:
  - **Custom Header**: Branded header with meal type info
  - **Aggregated Summary Card**:
    - Total nutrition for all meals in the type
    - Macronutrients with icons
    - Vitamins & Minerals grid (when available)
  - **Individual Meals List**:
    - Each meal displayed as a card
    - Tap to open `MealDetailView`
    - Shows time, name, calories, macros
    - Photo indicator if available

### 4. Updated Meals List View (`NutritionView.swift`)
- **Changes**:
  - Replaced flat meal list with meal type grouping
  - Added horizontal scrolling page view for meal type cards
  - Each card width is (screen width - 48px) for nice spacing
  - Updated "Recent Meals" preview to show grouped meals
  - Added state management for meal type detail navigation

## User Flow

### Main Nutrition View
1. User opens Nutrition tab
2. Sees "Today's Meals by Type" section
3. Shows top 2 meal type groups as compact cards
4. Tap "See All" to navigate to full meals list

### Meals List View
1. Shows date picker
2. Horizontal scrollable page view of meal type cards
3. Each card shows:
   - Meal type emoji and name
   - Meal count
   - Total calories (prominent)
   - Macronutrients grid
4. Swipe left/right to view different meal types

### Meal Type Summary
1. Tap a meal type card
2. Opens sheet with:
   - Custom header with meal type info
   - Aggregated summary of all nutrition
   - List of individual meals
3. Tap individual meal → opens `MealDetailView`

## UI/UX Highlights

### Design Consistency
- Uses existing Zivo brand colors (zivoRed gradient)
- Consistent card styling with shadows
- Familiar nutrition badges and icons
- Smooth sheet presentations

### Visual Hierarchy
- **Level 1**: Meal Type Cards (Page View)
  - Large emoji
  - Prominent calories
  - 4-column macro grid
  
- **Level 2**: Meal Type Summary
  - Detailed aggregated summary
  - Individual meal cards with tap targets
  
- **Level 3**: Meal Detail View (existing)
  - Full nutritional breakdown
  - Image viewing
  - All vitamins & minerals

### Responsive Design
- Cards adapt to screen width
- Horizontal scrolling prevents overcrowding
- Proper safe area handling
- Support for both portrait and landscape

## Technical Implementation

### Key Components
```swift
// Model
struct MealTypeGroup: Identifiable {
    let mealType: MealType
    let meals: [NutritionDataResponse]
    // Computed properties for aggregated nutrition
}

// Extension for easy grouping
extension Array where Element == NutritionDataResponse {
    func groupedByMealType() -> [MealTypeGroup]
}

// Views
- MealTypeCard: Level 1 card component
- MealTypeSummaryView: Level 2 detail view
- Updated MealsListView: Container with page view
```

### State Management
```swift
@State private var showingMealTypeSummary = false
@State private var selectedMealTypeGroup: MealTypeGroup?
@State private var showingMealTypeDetail = false
@State private var selectedMealTypeGroupForDetail: MealTypeGroup?
```

### Navigation Pattern
- Uses SwiftUI sheets for modals
- Smooth transitions between levels
- Back buttons with branded styling
- Maintains navigation stack properly

## Benefits

### For Users
1. **Better Organization**: Meals grouped logically by type
2. **Quick Overview**: See totals at a glance
3. **Easy Navigation**: Swipe between meal types
4. **Context Aware**: Understand meal distribution throughout day

### For Developers
1. **Reusable Components**: Modular card and view design
2. **Maintainable**: Clear separation of concerns
3. **Extensible**: Easy to add more aggregations
4. **Type Safe**: Leverages Swift's type system

## Files Modified
1. `apps/iOS/Zivohealth/Sources/Views/NutritionView.swift`
   - Added meal type grouping logic
   - Updated recent meals preview
   - Added navigation state management

## Files Created
1. `apps/iOS/Zivohealth/Sources/Models/MealTypeGroup.swift`
2. `apps/iOS/Zivohealth/Sources/Views/MealTypeCard.swift`
3. `apps/iOS/Zivohealth/Sources/Views/MealTypeSummaryView.swift`

## Future Enhancements
1. Add meal type filtering in charts
2. Compare nutrition across meal types
3. Goal tracking per meal type
4. Meal type recommendations based on targets
5. Export meal type reports

