def render_commands(commands):
    if not commands:
        return """
        <section>
          <h2>Steps and Commands</h2>
          <p>No command data was supplied for this tutorial.</p>
        </section>
        """

    # ---------------------------------------------------------
    # WMIC -> PowerShell comparison mode
    # ---------------------------------------------------------

    comparison_mode = any(
        isinstance(item, dict)
        and (
            "wmic" in item
            or "powershell" in item
        )
        for item in commands
    )

    if comparison_mode:
        rows = []

        for item in commands:
            if not isinstance(item, dict):
                continue

            purpose = esc(
                item.get(
                    "purpose",
                    "Command"
                )
            )

            wmic = esc(
                item.get(
                    "wmic",
                    ""
                )
            )

            powershell = esc(
                item.get(
                    "powershell",
                    ""
                )
            )

            rows.append(
                f"""
                <tr>
                  <td>{purpose}</td>
                  <td><code>{wmic}</code></td>
                  <td><code>{powershell}</code></td>
                </tr>
                """
            )

        return f"""
        <section>
          <h2>Commands Used in This Tutorial</h2>

          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Purpose</th>
                  <th>Old WMIC Command</th>
                  <th>PowerShell Replacement</th>
                </tr>
              </thead>

              <tbody>
                {''.join(rows)}
              </tbody>
            </table>
          </div>
        </section>
        """

    # ---------------------------------------------------------
    # General troubleshooting mode
    # ---------------------------------------------------------

    sections = []

    for number, item in enumerate(
        commands,
        start=1
    ):
        if isinstance(item, str):
            purpose = f"Command {number}"
            command = item
            note = ""
            warning = ""

        elif isinstance(item, dict):
            purpose = item.get(
                "purpose",
                f"Step {number}"
            )

            command = item.get(
                "command",
                ""
            )

            note = item.get(
                "note",
                ""
            )

            warning = item.get(
                "warning",
                ""
            )

        else:
            continue

        note_html = ""

        if note:
            note_html = f"""
            <p>
              {esc(note)}
            </p>
            """

        warning_html = ""

        if warning:
            warning_html = f"""
            <div class="preview-warning">
              <strong>Important</strong>
              {esc(warning)}
            </div>
            """

        sections.append(
            f"""
            <div class="command-step">

              <h3>
                {number}. {esc(purpose)}
              </h3>

              <pre><code>{esc(command)}</code></pre>

              {note_html}

              {warning_html}

            </div>
            """
        )

    return f"""
    <section>

      <h2>Step-by-Step Commands Used in This Tutorial</h2>

      {''.join(sections)}

    </section>
    """
