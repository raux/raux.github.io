# Raula Gaikovina Kula - Academic Website

This is the personal academic and research website for Professor Raula Gaikovina Kula.

## About

This site is built using [Hugo](https://gohugo.io/) static site generator with the [NewBee](themes/NewBee) theme.

## Local Development

### Prerequisites

- [Hugo](https://gohugo.io/installation/) (Extended version recommended)
- Git

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/raux/raux.github.io.git
   cd raux.github.io
   ```

2. Run the development server:
   ```bash
   hugo server -D
   ```

3. Open your browser to `http://localhost:1313`

### Building

To build the static site:
```bash
hugo
```

The generated site will be in the `public/` directory.

## Content Management

### Adding a New Post

Create a new post in the `content/posts/` directory:
```bash
hugo new posts/my-new-post.md
```

Edit the post with your content and update the front matter as needed.

### About Page

Edit the about page at `content/about/index.md`.

## Custom Shortcodes

This site includes several custom Hugo shortcodes in `layouts/shortcodes/`:

- **naist.html** / **naist3.html**: Custom shortcodes for displaying NAIST-related content
- **dynalist.html**: Embed Dynalist content
- **GHStar.html**: Display GitHub repository star button
- **details.html**: Expandable details/summary sections
- **math.html**: Mathematical notation support
- **mermaid.html**: Mermaid diagram support

### Usage Examples

```markdown
{{< naist >}}
{{< dynalist "list-id" >}}
{{< GHStar "username/repo" >}}
{{< details "Summary Title" >}}
Content here
{{< /details >}}
```

## Configuration

Main configuration is in `hugo.toml`. Key settings:

- Site title, author info, and social links
- Menu configuration
- Theme settings and parameters
- Markup and syntax highlighting options

## Deployment

This site is automatically deployed to GitHub Pages via GitHub Actions when changes are pushed to the main branch.

## License

See [LICENSE](LICENSE) file for details.

## Theme

This site uses the NewBee theme. See [themes/NewBee/README.md](themes/NewBee/README.md) for theme documentation.