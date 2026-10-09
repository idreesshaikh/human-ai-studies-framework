/*

Welcome to the GitHub Copilot study!
Your mission, should you choose to accept it:

Write a toy HTTP server engine.
You do not need to actually handle network requests.
Just parse a request string and return a response string.

This is a good reference for the structure of HTTP requests and responses:
https://developer.mozilla.org/en-US/docs/Web/HTTP/Messages

You must parse the request headers, but you do not need to validate them.
You must return a valid HTTP response with a correct content length.
You must serve files from the content/ directory as the root.
  Meaning, `GET /index.html HTTP/1.1` should return content/index.html.
  You do not need to handle `GET /`

Return HTTP status 404 if the file is not found.
Return HTTP status 400 if the request is invalid.
Return HTTP status 405 for any HTTP method other than GET.
Return HTTP status 200 with the contents of the file if the request is valid.

A proper HTTP response with no body has two trailing newlines:
  `HTTP/1.1 404 Not Found\n\n`

A proper HTTP response with a body has a Content-Length header and a body:
  `HTTP/1.1 200 OK\nContent-Length: ${THELENGTH}\n\n${THEFILEBODY}`

*/

const fs = require('node:fs');
const path = require('node:path');

const CONTENT_DIR = path.join(__dirname, 'content');

/**
 * Take a raw HTTP request string and return the raw HTTP response string.
 * This is the function the tests call.
 * @param {string} request e.g. "GET /index.html HTTP/1.1\r\nHost: localhost\r\n\r\n"
 * @returns {string}
 */
function handleRequest(request) {
  // YOUR CODE HERE
}

/**
 * Parse a raw request string into its parts.
 * Return null if the request is invalid.
 * @param {string} request
 * @returns {{ method: string, path: string, version: string, headers: Record<string, string> } | null}
 */
function parseRequest(request) {
  // YOUR CODE HERE
}

/**
 * Build a response string for the given status.
 * With no body: `HTTP/1.1 ${status} ${reason}\n\n`
 * With a body:  `HTTP/1.1 ${status} ${reason}\nContent-Length: ${n}\n\n${body}`
 * @param {number} status
 * @param {string} reason
 * @param {string} [body]
 * @returns {string}
 */
function buildResponse(status, reason, body) {
  // YOUR CODE HERE
}

/**
 * Read a file below content/. Return its contents as a string, or null if it does not exist.
 * @param {string} urlPath e.g. "/index.html"
 * @returns {string | null}
 */
function readContentFile(urlPath) {
  // YOUR CODE HERE
}

module.exports = { handleRequest, parseRequest, buildResponse, readContentFile, CONTENT_DIR };
