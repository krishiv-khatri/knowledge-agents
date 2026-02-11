import re
from typing import List, Tuple, Optional
from dataclasses import dataclass, field

"""
This is mainly for testing - most of the functionality is just copied to util
"""

@dataclass
class TableInfo:
    """Information about a detected table in markdown"""
    start_pos: int
    end_pos: int
    header_row: str
    separator_row: str
    data_rows: List[str]
    title: Optional[str] = None


class MarkdownTableSplitter:
    """
    A class to detect and split markdown tables into row-based chunks.
    
    This splitter preserves table headers in each chunk and adds numbered titles
    to each split section while maintaining all other markdown content.
    """
    
    def __init__(self, rows_per_chunk: int = 10, chunk_title_template: str = "Part {chunk_num}"):
        """
        Initialize the table splitter.
        
        Args:
            rows_per_chunk: Number of data rows per chunk (excluding header)
            chunk_title_template: Template for chunk titles, use {chunk_num} for numbering
        """
        self.rows_per_chunk = rows_per_chunk
        self.chunk_title_template = chunk_title_template
    
    def _extract_table_title(self, content_before_table: str) -> Optional[str]:
        """
        Extract a title from the content immediately before a table.
        Looks for the last heading before the table.
        
        Args:
            content_before_table: Content that appears before the table
            
        Returns:
            The extracted title or None if no suitable title found
        """
        if not content_before_table.strip():
            return None
            
        # Look for the last heading (# ## ### etc.) before the table
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        headings = list(heading_pattern.finditer(content_before_table))
        
        if headings:
            last_heading = headings[-1]
            return last_heading.group(2).strip()
        
        return None
    
    def _find_tables(self, markdown_content: str) -> List[TableInfo]:
        """
        Find tables using a simple line-by-line approach.
        A table is: header_row, separator_row, data_rows...
        """
        lines = markdown_content.split('\n')
        tables = []
        i = 0
        
        while i < len(lines) - 1:  # Need at least header + separator
            line = lines[i].strip()
            
            # Check if this could be a header row (contains |)
            if '|' in line and line.count('|') >= 2:  # At least 2 pipes for a valid table
                header_row = line
                
                # Check next line for separator (contains | and -)
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if '|' in next_line and '-' in next_line:
                        separator_row = next_line
                        
                        # Now collect data rows
                        data_rows = []
                        j = i + 2
                        
                        while j < len(lines):
                            data_line = lines[j].strip()
                            # If line contains |, it's likely a table row
                            if '|' in data_line:
                                # Skip completely empty rows between pipes
                                content_between_pipes = data_line.replace('|', '').strip()
                                if content_between_pipes:  # Has actual content
                                    data_rows.append(data_line)
                            else:
                                # No pipe found, end of table
                                break
                            j += 1
                        
                        # Only consider it a valid table if we have data rows
                        if data_rows:
                            # Calculate positions in original text
                            start_pos = sum(len(lines[k]) + 1 for k in range(i))  # +1 for newline
                            end_pos = sum(len(lines[k]) + 1 for k in range(j))
                            
                            # Extract title
                            content_before = '\n'.join(lines[:i])
                            title = self._extract_table_title(content_before)
                            
                            table_info = TableInfo(
                                start_pos=start_pos,
                                end_pos=end_pos,
                                header_row=header_row,
                                separator_row=separator_row,
                                data_rows=data_rows,
                                title=title
                            )
                            tables.append(table_info)
                            
                            # Skip past this table
                            i = j
                            continue
            
            i += 1
        
        return tables
    
    def _split_table_into_chunks(self, table_info: TableInfo) -> List[str]:
        """
        Split a single table into chunks with preserved headers.
        
        Args:
            table_info: Information about the table to split
            
        Returns:
            List of markdown strings, each containing a table chunk
        """
        chunks = []
        data_rows = table_info.data_rows
        base_title = table_info.title or "Table"
        
        # Calculate total chunks needed
        total_chunks = (len(data_rows) + self.rows_per_chunk - 1) // self.rows_per_chunk
        
        # Always use consistent numbering, even for single chunks
        for chunk_idx in range(total_chunks):
            start_row = chunk_idx * self.rows_per_chunk
            end_row = min(start_row + self.rows_per_chunk, len(data_rows))
            chunk_data_rows = data_rows[start_row:end_row]
            
            # Create chunk title - always include part number if more than 1 chunk
            if total_chunks > 1:
                chunk_title_text = self.chunk_title_template.format(
                    chunk_num=chunk_idx + 1,
                    total_chunks=total_chunks
                )
                chunk_title = f"**{base_title} - {chunk_title_text}**"
            else:
                # Single chunk - just use the base title
                chunk_title = f"**{base_title}**"
            
            # Build the chunk content with header preserved
            table_content = f"{table_info.header_row}\n{table_info.separator_row}\n" + \
                          '\n'.join(chunk_data_rows)
            
            chunk = f"## {chunk_title}\n\n{table_content}"
            chunks.append(chunk)
        
        return chunks
    
    def split_markdown_tables(self, markdown_content: str) -> str:
        """
        Process markdown content and split all tables into chunks.
        
        Args:
            markdown_content: The original markdown string
            
        Returns:
            Modified markdown string with tables split into chunks
        """
        if not markdown_content or not markdown_content.strip():
            return markdown_content
        
        # Find all tables using simple approach
        tables = self._find_tables(markdown_content)
        
        if not tables:
            return markdown_content
        
        # Process tables from end to start to maintain position indices
        result = markdown_content
        
        for table_info in reversed(tables):
            # Split this table into chunks
            chunks = self._split_table_into_chunks(table_info)
            
            # Replace the original table with chunks
            chunks_text = '\n\n'.join(chunks)
            
            # Replace in the result using positions
            result = result[:table_info.start_pos] + chunks_text + result[table_info.end_pos:]
        
        return result


# Convenience function for easy integration
def split_markdown_tables(markdown_content: str, rows_per_chunk: int = 10, 
                         chunk_title_template: str = "Part {chunk_num}") -> str:
    """
    Convenience function to split markdown tables in a single call.
    
    Args:
        markdown_content: The markdown string to process
        rows_per_chunk: Number of data rows per chunk (default: 10)
        chunk_title_template: Template for chunk titles (default: "Part {chunk_num}")
        
    Returns:
        Modified markdown string with tables split into chunks
    """
    splitter = MarkdownTableSplitter(rows_per_chunk, chunk_title_template)
    return splitter.split_markdown_tables(markdown_content)


def test_table_splitter():
    """Test the table splitter with the user's problematic table format."""
    
    # Test with the exact problematic table format from user
    sample_markdown = """


"""
    
    print("ORIGINAL:")
    print(sample_markdown)
    print("\n" + "="*50 + "\n")
    
    # Split tables with 5 rows per chunk
    result = split_markdown_tables(sample_markdown, rows_per_chunk=5)
    print("RESULT:")
    print(result)
    print("\n" + "="*50 + "\n")


if __name__ == "__main__":
    test_table_splitter()