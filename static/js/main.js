document.getElementById('recommendationForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const form = e.target;
    const submitButton = form.querySelector('button');
    const recommendationsDiv = document.getElementById('recommendations');
    
    // Disable button and show loading state
    submitButton.disabled = true;
    submitButton.textContent = 'Getting Recommendations...';
    recommendationsDiv.innerHTML = 'Loading...';
    
    try {
        const response = await fetch('/get_recommendations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                restrictions: form.restrictions.value,
                requests: form.requests.value,
                dietType: form.dietType.value,
                region: form.region.value,
                priceRange: form.priceRange.value
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const recipes = parseRecommendations(data.recommendations);
            recommendationsDiv.innerHTML = `
                <h2>Your Recommendations</h2>
                <div class="recommendations-text">
                    ${data.recommendations.split('Recipe').map((recipe, index) => {
                        if (index === 0) return ''; // Skip the first empty split
                        const parsedRecipe = recipes[index - 1]; // Get the parsed recipe for the name
                        const recipeName = parsedRecipe ? `: ${parsedRecipe.name}` : '';
                        
                        // Remove the number and name from the content since we're showing it in the header
                        const cleanedRecipe = recipe
                            .replace(/^\d+:.*?\n/, '') // Remove the "1: Recipe Name" line
                            .replace(/\n/g, '<br>');   // Convert newlines to <br>
                        
                        return `<div class="recipe-section">
                            <h3>Recipe ${index}${recipeName}</h3>
                            <div class="recipe-content">
                                ${cleanedRecipe}
                            </div>
                            <button class="save-recipe-btn" data-recipe-index="${index-1}">
                                Save This Recipe
                            </button>
                        </div>`;
                    }).join('')}
                </div>
                <a href="/saved_recipes" class="view-saved-btn secondary-btn">View Saved Recipes</a>
            `;
            
            // Add click handlers for save buttons
            document.querySelectorAll('.save-recipe-btn').forEach((button) => {
                button.onclick = async () => {
                    try {
                        const recipeIndex = button.dataset.recipeIndex;
                        const recipes = parseRecommendations(data.recommendations);
                        const recipe = recipes[recipeIndex];
                        
                        // Get the form element
                        const recommendationForm = document.getElementById('recommendationForm');
                        
                        // Clean the recipe name - remove the "Recipe X:" prefix if present
                        if (recipe.name.includes(':')) {
                            recipe.name = recipe.name.split(':')[1].trim();
                        }
                        
                        const recipeToSave = {
                            name: recipe.name,
                            description: recipe.description,
                            ingredients: recipe.ingredients,
                            cost: recipe.cost,
                            diet_type: recommendationForm.dietType.value,
                            region: recommendationForm.region.value,
                            nutrition: recipe.nutrition,
                            servings: recipe.servings,
                            restrictions: recommendationForm.restrictions.value
                        };
                        
                        console.log('Sending to server:', recipeToSave); // Debug log
                        
                        const response = await fetch('/save_recipe', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify(recipeToSave)
                        });
                        
                        const result = await response.json();
                        if (result.success) {
                            alert('Recipe saved successfully!');
                            button.textContent = 'Saved!';
                            button.disabled = true;
                        } else {
                            alert('Failed to save recipe: ' + result.error);
                        }
                    } catch (error) {
                        console.error('Error saving recipe:', error);
                        alert('Error saving recipe: ' + error);
                    }
                };
            });
        } else {
            recommendationsDiv.innerHTML = `
                <div class="error">
                    Failed to get recommendations. Please try again.
                </div>
            `;
        }
    } catch (error) {
        recommendationsDiv.innerHTML = `
            <div class="error">
                An error occurred. Please try again later.
            </div>
        `;
    } finally {
        // Reset button state
        submitButton.disabled = false;
        submitButton.textContent = 'Get Recommendations';
    }
});

function createSaveButton(recipe) {
    const button = document.createElement('button');
    button.className = 'save-recipe-btn';
    button.textContent = 'Save Recipe';
    button.onclick = async () => {
        try {
            console.log('Saving recipe:', recipe); // Debug log
            
            const response = await fetch('/save_recipe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(recipe)
            });
            
            const result = await response.json();
            console.log('Save result:', result); // Debug log
            
            if (result.success) {
                alert('Recipe saved successfully!');
                button.textContent = 'Saved!';
                button.disabled = true;
            } else {
                alert('Failed to save recipe: ' + result.error);
            }
        } catch (error) {
            console.error('Error saving recipe:', error); // Debug log
            alert('Error saving recipe: ' + error);
        }
    };
    return button;
}

function parseRecommendations(text) {
    const recipes = [];
    const sections = text.split(/Recipe \d+:/g).filter(section => section.trim());
    
    // Get form values once outside the loop
    const form = document.getElementById('recommendationForm');
    const dietType = form.dietType.value;
    const region = form.region.value;
    
    sections.forEach((section, index) => {
        try {
            const recipe = {
                name: '',
                description: '',
                servings: '',
                nutrition: {
                    calories: '',
                    protein: '',
                    carbs: '',
                    fat: ''
                },
                ingredients: '',
                cost: '',
                diet_type: dietType,  // Use snake_case to match backend
                region: region
            };
            
            const lines = section.split('\n').map(line => line.trim()).filter(Boolean);
            
            // First line after splitting should be the recipe name
            if (lines[0] && !lines[0].startsWith('Description:')) {
                recipe.name = lines[0].trim();
            }
            
            let currentSection = '';
            
            lines.forEach(line => {
                if (line.startsWith('Description:')) {
                    currentSection = 'description';
                    recipe.description = line.replace('Description:', '').trim();
                }
                else if (line.startsWith('Servings:')) {
                    currentSection = '';
                    recipe.servings = line.replace('Servings:', '').trim();
                }
                else if (line.startsWith('Nutritional Facts')) {
                    currentSection = 'nutrition';
                }
                else if (line.startsWith('Ingredients:')) {
                    currentSection = 'ingredients';
                    recipe.ingredients = '';
                }
                else if (line.startsWith('Approximate Cost Per Serving:')) {
                    currentSection = '';
                    recipe.cost = line.replace('Approximate Cost Per Serving:', '').trim();
                }
                else if (line.startsWith('•')) {
                    if (currentSection === 'ingredients') {
                        recipe.ingredients += (recipe.ingredients ? '\n' : '') + line.trim();
                    }
                }
                else if (currentSection === 'nutrition') {
                    if (line.includes('Calories:')) {
                        recipe.nutrition.calories = line.split(':')[1].trim();
                    }
                    else if (line.includes('Protein:')) {
                        recipe.nutrition.protein = line.split(':')[1].trim();
                    }
                    else if (line.includes('Carbs:')) {
                        recipe.nutrition.carbs = line.split(':')[1].trim();
                    }
                    else if (line.includes('Fat:')) {
                        recipe.nutrition.fat = line.split(':')[1].trim();
                    }
                }
                else if (currentSection === 'description' && !line.includes(':')) {
                    recipe.description += ' ' + line;
                }
            });
            
            recipe.description = recipe.description.replace(/\s+/g, ' ').trim();
            recipe.ingredients = recipe.ingredients.trim();
            
            if (recipe.name && recipe.description && recipe.ingredients) {
                recipes.push(recipe);
            }
        } catch (error) {
            console.error('Error parsing recipe section:', error);
        }
    });
    
    console.log('Parsed recipes:', recipes); // Debug log
    return recipes;
}

// Add this function to handle the toggle
function toggleNutrition(button) {
    button.classList.toggle('active');
    const content = button.nextElementSibling;
    content.classList.toggle('show');
}

// Add the toggle function to the window object so it's accessible from the onclick handler
window.toggleNutrition = toggleNutrition; 