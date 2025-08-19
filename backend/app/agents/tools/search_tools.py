"""
Search Tools for Medical Information Retrieval

This module provides reusable web search and medical information tools for all agents.
"""

from typing import List
from langchain.tools import Tool
import os


class SearchToolkit:
    """Centralized search toolkit for medical and web information"""
    
    def __init__(self):
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
    
    def get_tools(self) -> List[Tool]:
        """Get all search tools"""
        return [self.get_medical_search_tool()]
    
    def get_medical_search_tool(self) -> Tool:
        """Medical information search tool"""
        def search_medical_info(query: str) -> str:
            """Search for medical information with fallback"""
            try:
                if self.tavily_api_key:
                    from langchain_community.tools import TavilySearchResults
                    search = TavilySearchResults(api_key=self.tavily_api_key)
                    results = search.run(f"medical {query}")
                    return str(results)
                else:
                    return f"Medical search for '{query}' - Please consult medical references."
            except Exception as e:
                return f"Search error: {str(e)}"
        
        return Tool(
            name="Medical_Search",
            func=search_medical_info,
            description="Search for medical information and guidelines"
        )
    
    def get_drug_info_tool(self) -> Tool:
        """Specialized drug information tool"""
        def search_drug_info(drug_name: str) -> str:
            """Search for specific drug information"""
            query = f"drug information {drug_name} side effects interactions dosage"
            
            try:
                if self.tavily_api_key:
                    from langchain_community.tools import TavilySearchResults
                    search = TavilySearchResults(api_key=self.tavily_api_key)
                    results = search.run(query)
                    return str(results)
                else:
                    return f"Drug information search for '{drug_name}' - API not configured. Please consult drug references or pharmacists."
            except Exception as e:
                return f"Drug search error: {str(e)}"
        
        return Tool(
            name="Drug_Information_Search",
            func=search_drug_info,
            description="Search for specific drug information including side effects, interactions, and dosage"
        )
    
    def get_lab_reference_tool(self) -> Tool:
        """Lab test reference ranges tool"""
        def search_lab_references(test_name: str) -> str:
            """Search for lab test reference ranges"""
            query = f"lab test {test_name} normal range reference values clinical significance"
            
            try:
                if self.tavily_api_key:
                    from langchain_community.tools import TavilySearchResults
                    search = TavilySearchResults(api_key=self.tavily_api_key)
                    results = search.run(query)
                    return str(results)
                else:
                    return f"Lab reference search for '{test_name}' - API not configured. Please consult lab reference guides."
            except Exception as e:
                return f"Lab reference search error: {str(e)}"
        
        return Tool(
            name="Lab_Reference_Search",
            func=search_lab_references,
            description="Search for lab test normal ranges, reference values, and clinical significance"
        )


def create_search_tools() -> List[Tool]:
    """Create and return all search tools"""
    toolkit = SearchToolkit()
    return toolkit.get_tools() 