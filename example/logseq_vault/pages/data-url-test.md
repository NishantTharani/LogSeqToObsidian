- This page tests data URL handling
- Here's an embedded image with a data URL:
  ![Small red dot](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==)
- The conversion should preserve this data URL without trying to copy it as a file
- Regular file assets should still work normally