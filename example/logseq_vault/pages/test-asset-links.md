# Asset Link Test Cases

This page contains test cases for different types of asset links:

## Local Asset (should be processed)
![Local Image](../assets/image_1688967926613_0.png)

## HTTP Link (should be skipped)
![HTTP Image](http://example.com/image.png)

## HTTPS Link (should be skipped)  
![HTTPS Image](https://example.com/secure-image.png)

## Regular text for context
These test cases help verify that the conversion script correctly:
- Processes local assets and copies them to attachments folder
- Skips HTTP/HTTPS links without attempting to process them as local files