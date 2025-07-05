"""
Few-Shot Examples System for Error Analysis

Provides structured examples for common error patterns to improve LLM performance
in error analysis and fix suggestions.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json
import re
from pathlib import Path

@dataclass
class ErrorExample:
    """A single error example with context and solution"""
    error_type: str
    error_pattern: str  # Regex pattern to match the error
    language: str
    description: str
    error_context: str  # Code context where error occurs
    fix_suggestion: str
    explanation: str
    confidence_score: float  # How confident we are in this pattern
    tags: List[str]  # Tags for categorization

@dataclass
class FewShotPrompt:
    """Complete few-shot prompt with examples"""
    system_prompt: str
    examples: List[ErrorExample]
    user_prompt_template: str

class FewShotExampleManager:
    """
    Manages few-shot examples for different error types and languages
    
    Provides intelligent example selection based on error patterns,
    language context, and confidence scores.
    """
    
    def __init__(self, examples_file: Optional[str] = None):
        self.examples: Dict[str, List[ErrorExample]] = {}
        self.language_examples: Dict[str, List[ErrorExample]] = {}
        
        # Load built-in examples
        self._load_builtin_examples()
        
        # Load custom examples if provided
        if examples_file and Path(examples_file).exists():
            self._load_custom_examples(examples_file)
    
    def _load_builtin_examples(self):
        """Load built-in examples for common error patterns"""
        
        # Python Examples
        python_examples = [
            ErrorExample(
                error_type="NameError",
                error_pattern=r"NameError: name '(\w+)' is not defined",
                language="python",
                description="Variable or function not defined",
                error_context="""
def calculate_total(items):
    total = 0
    for item in items:
        total += item.price
    return total_amount  # Error: total_amount not defined
""",
                fix_suggestion="return total  # Use the correct variable name",
                explanation="The variable 'total_amount' is not defined. The correct variable name is 'total'.",
                confidence_score=0.95,
                tags=["variable", "typo", "scope"]
            ),
            
            ErrorExample(
                error_type="AttributeError",
                error_pattern=r"AttributeError: '(\w+)' object has no attribute '(\w+)'",
                language="python",
                description="Accessing non-existent attribute",
                error_context="""
class User:
    def __init__(self, name):
        self.name = name

user = User("Alice")
print(user.email)  # Error: User has no attribute 'email'
""",
                fix_suggestion="""
# Option 1: Add the attribute to the class
class User:
    def __init__(self, name, email=None):
        self.name = name
        self.email = email

# Option 2: Check if attribute exists
if hasattr(user, 'email'):
    print(user.email)
else:
    print("No email set")
""",
                explanation="The User class doesn't have an 'email' attribute. Either add it to the class or check for its existence.",
                confidence_score=0.90,
                tags=["attribute", "class", "missing_property"]
            ),
            
            ErrorExample(
                error_type="TypeError",
                error_pattern=r"TypeError: unsupported operand type\(s\) for \+: '(\w+)' and '(\w+)'",
                language="python",
                description="Type mismatch in operations",
                error_context="""
def add_values(a, b):
    return a + b

result = add_values("5", 3)  # Error: can't add string and int
""",
                fix_suggestion="""
def add_values(a, b):
    # Convert to same type
    return int(a) + int(b)  # or str(a) + str(b) depending on intent
""",
                explanation="Cannot add string and integer. Convert both to the same type before operation.",
                confidence_score=0.92,
                tags=["type", "conversion", "operation"]
            )
        ]
        
        # JavaScript Examples
        javascript_examples = [
            ErrorExample(
                error_type="ReferenceError",
                error_pattern=r"ReferenceError: (\w+) is not defined",
                language="javascript",
                description="Variable or function not defined",
                error_context="""
function calculateTotal(items) {
    let total = 0;
    for (let item of items) {
        total += item.price;
    }
    return totalAmount;  // Error: totalAmount not defined
}
""",
                fix_suggestion="return total;  // Use the correct variable name",
                explanation="The variable 'totalAmount' is not defined. The correct variable name is 'total'.",
                confidence_score=0.95,
                tags=["variable", "typo", "scope"]
            ),
            
            ErrorExample(
                error_type="TypeError",
                error_pattern=r"TypeError: Cannot read propert(y|ies) '(\w+)' of (null|undefined)",
                language="javascript",
                description="Accessing property of null/undefined",
                error_context="""
function getUserEmail(user) {
    return user.email;  // Error if user is null/undefined
}

const email = getUserEmail(null);
""",
                fix_suggestion="""
function getUserEmail(user) {
    // Option 1: Guard clause
    if (!user) return null;
    return user.email;
    
    // Option 2: Optional chaining (ES2020+)
    return user?.email;
    
    // Option 3: Default parameter
    return (user || {}).email;
}
""",
                explanation="Check if the object exists before accessing its properties to avoid null/undefined errors.",
                confidence_score=0.93,
                tags=["null_check", "property_access", "defensive_programming"]
            ),
            
            ErrorExample(
                error_type="SyntaxError",
                error_pattern=r"SyntaxError: Unexpected token '(\w+)'",
                language="javascript",
                description="Syntax error in code",
                error_context="""
const items = [
    { name: "item1", price: 10 },
    { name: "item2", price: 20 },  // Missing closing bracket
""",
                fix_suggestion="""
const items = [
    { name: "item1", price: 10 },
    { name: "item2", price: 20 }
];  // Add missing closing bracket and semicolon
""",
                explanation="Missing closing bracket for array declaration. Check for balanced brackets and proper syntax.",
                confidence_score=0.88,
                tags=["syntax", "brackets", "array"]
            )
        ]
        
        # Java Examples
        java_examples = [
            ErrorExample(
                error_type="NullPointerException",
                error_pattern=r"NullPointerException",
                language="java",
                description="Accessing method/field on null object",
                error_context="""
public class User {
    private String name;
    
    public String getEmail() {
        return name.toLowerCase() + "@example.com";  // Error if name is null
    }
}
""",
                fix_suggestion="""
public String getEmail() {
    if (name == null) {
        return null;  // or throw appropriate exception
    }
    return name.toLowerCase() + "@example.com";
    
    // Or use Optional (Java 8+)
    return Optional.ofNullable(name)
        .map(n -> n.toLowerCase() + "@example.com")
        .orElse(null);
}
""",
                explanation="Check for null before calling methods on objects. Use defensive programming or Optional.",
                confidence_score=0.94,
                tags=["null_check", "defensive_programming", "optional"]
            ),
            
            ErrorExample(
                error_type="ArrayIndexOutOfBoundsException",
                error_pattern=r"ArrayIndexOutOfBoundsException: Index (\d+) out of bounds for length (\d+)",
                language="java",
                description="Array index exceeds array bounds",
                error_context="""
public void processItems(String[] items) {
    for (int i = 0; i <= items.length; i++) {  // Error: <= should be <
        System.out.println(items[i]);
    }
}
""",
                fix_suggestion="""
public void processItems(String[] items) {
    // Fix 1: Correct loop condition
    for (int i = 0; i < items.length; i++) {
        System.out.println(items[i]);
    }
    
    // Fix 2: Enhanced for loop (safer)
    for (String item : items) {
        System.out.println(item);
    }
    
    // Fix 3: Bounds checking
    for (int i = 0; i < items.length; i++) {
        if (i < items.length) {
            System.out.println(items[i]);
        }
    }
}
""",
                explanation="Array index out of bounds. Use < instead of <= in loop condition, or use enhanced for loop.",
                confidence_score=0.96,
                tags=["array", "bounds", "loop", "index"]
            )
        ]
        
        # Rust Examples
        rust_examples = [
            ErrorExample(
                error_type="BorrowError",
                error_pattern=r"cannot borrow .* as mutable because it is also borrowed as immutable",
                language="rust",
                description="Borrow checker violation",
                error_context="""
fn process_data(data: &mut Vec<i32>) {
    let first = &data[0];  // Immutable borrow
    data.push(42);         // Error: Mutable borrow while immutable borrow exists
    println!("{}", first);
}
""",
                fix_suggestion="""
fn process_data(data: &mut Vec<i32>) {
    // Option 1: Copy the value instead of borrowing
    let first = data[0];  // Copy instead of borrow
    data.push(42);
    println!("{}", first);
    
    // Option 2: Limit scope of immutable borrow
    {
        let first = &data[0];
        println!("{}", first);
    }  // Immutable borrow ends here
    data.push(42);  // Now mutable borrow is allowed
}
""",
                explanation="Rust's borrow checker prevents simultaneous mutable and immutable borrows. Copy the value or limit borrow scope.",
                confidence_score=0.91,
                tags=["borrow_checker", "ownership", "lifetime"]
            )
        ]
        
        # Store examples by error type and language
        all_examples = python_examples + javascript_examples + java_examples + rust_examples
        
        for example in all_examples:
            # Store by error type
            if example.error_type not in self.examples:
                self.examples[example.error_type] = []
            self.examples[example.error_type].append(example)
            
            # Store by language
            if example.language not in self.language_examples:
                self.language_examples[example.language] = []
            self.language_examples[example.language].append(example)
    
    def _load_custom_examples(self, examples_file: str):
        """Load custom examples from JSON file"""
        try:
            with open(examples_file, 'r') as f:
                custom_data = json.load(f)
            
            for example_data in custom_data.get('examples', []):
                example = ErrorExample(**example_data)
                
                if example.error_type not in self.examples:
                    self.examples[example.error_type] = []
                self.examples[example.error_type].append(example)
                
                if example.language not in self.language_examples:
                    self.language_examples[example.language] = []
                self.language_examples[example.language].append(example)
                
        except Exception as e:
            print(f"Failed to load custom examples from {examples_file}: {e}")
    
    def get_examples_for_error(self, 
                             error_text: str, 
                             language: Optional[str] = None,
                             max_examples: int = 3) -> List[ErrorExample]:
        """
        Get relevant examples for a specific error
        
        Args:
            error_text: The error message or description
            language: Programming language (optional)
            max_examples: Maximum number of examples to return
            
        Returns:
            List of relevant ErrorExample objects
        """
        relevant_examples = []
        
        # First, try to match by error pattern
        for error_type, examples in self.examples.items():
            for example in examples:
                if re.search(example.error_pattern, error_text, re.IGNORECASE):
                    if not language or example.language == language:
                        relevant_examples.append(example)
        
        # If no pattern matches, try keyword matching
        if not relevant_examples:
            error_keywords = set(re.findall(r'\w+', error_text.lower()))
            
            for error_type, examples in self.examples.items():
                for example in examples:
                    example_keywords = set(re.findall(r'\w+', 
                        f"{example.description} {' '.join(example.tags)}".lower()))
                    
                    # Calculate similarity based on common keywords
                    common_keywords = error_keywords.intersection(example_keywords)
                    if len(common_keywords) >= 2:  # At least 2 common keywords
                        if not language or example.language == language:
                            relevant_examples.append(example)
        
        # Sort by confidence score and return top examples
        relevant_examples.sort(key=lambda x: x.confidence_score, reverse=True)
        return relevant_examples[:max_examples]
    
    def get_examples_for_language(self, 
                                language: str, 
                                max_examples: int = 5) -> List[ErrorExample]:
        """Get examples for a specific programming language"""
        examples = self.language_examples.get(language, [])
        examples.sort(key=lambda x: x.confidence_score, reverse=True)
        return examples[:max_examples]
    
    def create_few_shot_prompt(self, 
                             error_text: str,
                             context: Dict[str, Any],
                             language: Optional[str] = None) -> FewShotPrompt:
        """
        Create a complete few-shot prompt for error analysis
        
        Args:
            error_text: The error to analyze
            context: Additional context (function, dependencies, etc.)
            language: Programming language
            
        Returns:
            FewShotPrompt with system prompt, examples, and user prompt
        """
        # Get relevant examples
        examples = self.get_examples_for_error(error_text, language, max_examples=3)
        
        # If no specific examples found, get general examples for the language
        if not examples and language:
            examples = self.get_examples_for_language(language, max_examples=2)
        
        # Create system prompt
        system_prompt = self._create_system_prompt(language, len(examples))
        
        # Create user prompt template
        user_prompt_template = self._create_user_prompt_template()
        
        return FewShotPrompt(
            system_prompt=system_prompt,
            examples=examples,
            user_prompt_template=user_prompt_template
        )
    
    def _create_system_prompt(self, language: Optional[str], num_examples: int) -> str:
        """Create system prompt for error analysis"""
        lang_specific = f" in {language}" if language else ""
        
        return f"""You are an expert software engineer specializing in error analysis and code debugging{lang_specific}.

Your task is to analyze code errors and provide comprehensive fix suggestions based on:
1. The error message and context
2. Function implementation details  
3. Usage patterns across the codebase
4. Dependencies and import relationships

I will provide you with {num_examples} examples of similar error patterns and their solutions.
Use these examples to guide your analysis, but adapt your response to the specific context provided.

For each error analysis, provide:
- Root cause explanation
- Specific fix suggestions with code examples
- Impact assessment on dependent files
- Confidence score (0.0 to 1.0)
- Risk level (low/medium/high)

Focus on practical, actionable solutions that consider the broader codebase context."""
    
    def _create_user_prompt_template(self) -> str:
        """Create user prompt template"""
        return """Please analyze this error:

ERROR: {error_text}

CONTEXT:
{context}

Based on the examples provided and the specific context, please provide:
1. Root cause analysis
2. Specific fix suggestions
3. Impact on dependent files
4. Risk assessment
5. Confidence score

Respond in JSON format matching the ImpactAnalysis schema."""
    
    def format_examples_for_prompt(self, examples: List[ErrorExample]) -> str:
        """Format examples for inclusion in LLM prompt"""
        if not examples:
            return "No specific examples available for this error pattern."
        
        formatted_examples = []
        
        for i, example in enumerate(examples, 1):
            formatted_example = f"""
EXAMPLE {i}: {example.error_type} in {example.language}
Description: {example.description}

Error Context:
{example.error_context}

Fix Suggestion:
{example.fix_suggestion}

Explanation: {example.explanation}
Confidence: {example.confidence_score}
Tags: {', '.join(example.tags)}
"""
            formatted_examples.append(formatted_example)
        
        return "\n".join(formatted_examples)
    
    def add_custom_example(self, example: ErrorExample):
        """Add a custom example to the manager"""
        if example.error_type not in self.examples:
            self.examples[example.error_type] = []
        self.examples[example.error_type].append(example)
        
        if example.language not in self.language_examples:
            self.language_examples[example.language] = []
        self.language_examples[example.language].append(example)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about loaded examples"""
        total_examples = sum(len(examples) for examples in self.examples.values())
        
        return {
            'total_examples': total_examples,
            'error_types': list(self.examples.keys()),
            'languages': list(self.language_examples.keys()),
            'examples_by_language': {
                lang: len(examples) for lang, examples in self.language_examples.items()
            },
            'examples_by_error_type': {
                error_type: len(examples) for error_type, examples in self.examples.items()
            },
            'average_confidence': sum(
                example.confidence_score 
                for examples in self.examples.values() 
                for example in examples
            ) / max(total_examples, 1)
        } 