import re
from datetime import datetime, timedelta
from searchat.models import ParsedQuery, DateFilter


class QueryParser:
    def parse(self, query: str) -> ParsedQuery:
        result = ParsedQuery(original=query)
        
        # Extract phrases in either single or double quotes
        result.exact_phrases = re.findall(r'"([^"]+)"|\'([^\']+)\'', query)
        # Flatten the tuples and remove empty strings
        result.exact_phrases = [phrase for pair in result.exact_phrases for phrase in pair if phrase]
        # Remove both types of quoted phrases from query
        query = re.sub(r'"[^"]+"', '', query)
        query = re.sub(r"'[^']+'", '', query)
        
        result.must_include = re.findall(r'\+(\w+)', query)
        query = re.sub(r'\+\w+', '', query)
        
        result.must_exclude = re.findall(r'-(\w+)', query)
        query = re.sub(r'-\w+', '', query)
        
        result.date_filter = self._extract_date_filter(query)
        query = self._remove_date_terms(query)
        
        if ' AND ' in query.upper():
            result.must_include.extend([
                term.strip() 
                for term in re.split(r'\s+AND\s+', query, flags=re.IGNORECASE)
                if term.strip()
            ])
        elif ' OR ' in query.upper():
            result.should_include = [
                term.strip() 
                for term in re.split(r'\s+OR\s+', query, flags=re.IGNORECASE)
                if term.strip()
            ]
        else:
            result.should_include = [term for term in query.split() if term.strip()]
        
        return result
    
    def _extract_date_filter(self, query: str) -> DateFilter | None:
        query_lower = query.lower()
        now = datetime.now()
        
        if 'today' in query_lower:
            return DateFilter(from_date=now.replace(hour=0, minute=0, second=0, microsecond=0), to_date=now)
        elif 'last week' in query_lower or 'last 7 days' in query_lower:
            return DateFilter(from_date=now - timedelta(days=7), to_date=now)
        elif 'last 30 days' in query_lower or 'last month' in query_lower:
            return DateFilter(from_date=now - timedelta(days=30), to_date=now)
        elif 'last 3 months' in query_lower:
            return DateFilter(from_date=now - timedelta(days=90), to_date=now)
        
        return None
    
    def _remove_date_terms(self, query: str) -> str:
        date_terms = [
            'today', 'last week', 'last 7 days', 'last 30 days', 
            'last month', 'last 3 months'
        ]
        
        result = query
        for term in date_terms:
            result = re.sub(rf'\b{term}\b', '', result, flags=re.IGNORECASE)
        
        return ' '.join(result.split())